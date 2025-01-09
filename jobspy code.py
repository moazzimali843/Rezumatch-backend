# First add the JOB_SEARCH_QUERY constant at the top of the file
JOB_SEARCH_QUERY = """
    query GetJobData {{
        jobSearch(
        {what}
        {location}
        limit: 100
        {cursor}
        sort: RELEVANCE
        {filters}
        ) {{
        pageInfo {{
            nextCursor
        }}
        results {{
            trackingKey
            job {{
            source {{
                name
            }}
            key
            title
            datePublished
            dateOnIndeed
            description {{
                html
            }}
            location {{
                countryName
                countryCode
                admin1Code
                city
                postalCode
                streetAddress
                formatted {{
                short
                long
                }}
            }}
            compensation {{
                estimated {{
                currencyCode
                baseSalary {{
                    unitOfWork
                    range {{
                    ... on Range {{
                        min
                        max
                    }}
                    }}
                }}
                }}
                baseSalary {{
                unitOfWork
                range {{
                    ... on Range {{
                    min
                    max
                    }}
                }}
                }}
                currencyCode
            }}
            attributes {{
                key
                label
            }}
            employer {{
                relativeCompanyPageUrl
                name
                dossier {{
                    employerDetails {{
                    addresses
                    industry
                    employeesLocalizedLabel
                    revenueLocalizedLabel
                    briefDescription
                    ceoName
                    ceoPhotoUrl
                    }}
                    images {{
                        headerImageUrl
                        squareLogoUrl
                    }}
                    links {{
                    corporateWebsite
                }}
                }}
            }}
            recruit {{
                viewJobUrl
                detailedSalary
                workSchedule
            }}
            }}
        }}
        }}
    }}
    """


from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import requests
import math
from typing import Optional, List
from bs4 import BeautifulSoup
import re, json, logging
logger = logging.getLogger(__name__)

# Enums and Constants
class CompensationInterval(Enum):
    HOURLY = "HOURLY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"

class JobType(Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    INTERNSHIP = "INTERNSHIP"

@dataclass
class Location:
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

@dataclass
class Compensation:
    interval: CompensationInterval
    min_amount: Optional[float]
    max_amount: Optional[float]
    currency: str

@dataclass
class JobPost:
    id: str
    title: str
    company_name: Optional[str]
    location: Location
    description: str
    compensation: Optional[Compensation]
    date_posted: str
    job_url: str
    job_type: List[JobType]
    is_remote: bool
    company_url: Optional[str] = None
    emails: Optional[List[str]] = None

class IndeedScraper:
    def __init__(self):
        self.session = requests.Session()
        self.api_url = "https://apis.indeed.com/graphql"
        self.jobs_per_page = 100
        self.seen_urls = set()
        self.api_headers = {
            "Host": "apis.indeed.com",
            "content-type": "application/json",
            "indeed-api-key": "161092c2017b5bbab13edb12461a62d5a833871e7cad6d9d475304573de67ac8",
            "accept": "*/*",
            "indeed-locale": "en-US",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Indeed App 193.1",
            "indeed-app-info": "appv=193.1; appid=com.indeed.jobsearch; osv=16.6.1; os=ios; dtype=phone",
            "indeed-co": "us",
            "origin": "https://www.indeed.com",
            "referer": "https://www.indeed.com/",
            "cookie": "INDEED_CSRF_TOKEN=random_token_here"  # You might need to get a valid token
        }

    def _scrape_page(self, search_term: str, location: str, cursor: Optional[str], is_remote: bool) -> tuple[List[JobPost], Optional[str]]:
        filters = self._build_filters(is_remote)
        
        # Properly format the GraphQL variables
        variables = {
            "what": search_term if search_term else "",
            "where": location if location else "",
            "cursor": cursor if cursor else None,
            "limit": self.jobs_per_page,
            "radius": 25,
            "radiusUnit": "MILES",
            "sort": "RELEVANCE"
        }

        # Format the GraphQL query properly
        query = {
            "query": JOB_SEARCH_QUERY,
            "variables": variables,
            "operationName": "GetJobData"
        }

        try:
            logger.debug(f"Sending request to Indeed API with headers: {json.dumps(self.api_headers, indent=2)}")
            logger.debug(f"Query: {json.dumps(query, indent=2)}")
            
            response = self.session.post(
                self.api_url,
                headers=self.api_headers,
                json=query,
                timeout=10
            )
            
            # Add debug logging
            logger.debug(f"Response status code: {response.status_code}")
            logger.debug(f"Response text: {response.text[:500]}...")  # Log first 500 chars
            
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}", exc_info=True)
            logger.error(f"Response content: {response.text if 'response' in locals() else 'No response'}")
            return [], None
        
    def search_jobs(self, search_term: str, location: str, results_wanted: int = 100, is_remote: bool = False):
        jobs = []
        cursor = None
        page = 1
        
        while len(self.seen_urls) < results_wanted:
            logger.info(f"Starting to scrape page {page}")
            try:
                new_jobs, cursor = self._scrape_page(search_term, location, cursor, is_remote)
                if not new_jobs:
                    logger.info("No more jobs found, ending search")
                    break
                jobs.extend(new_jobs)
                logger.info(f"Successfully scraped {len(new_jobs)} jobs from page {page}")
                page += 1
            except Exception as e:
                logger.error(f"Error during job search on page {page}: {str(e)}", exc_info=True)
                break
            
        return jobs[:results_wanted]
    
    def _build_filters(self, is_remote: bool):
        filters = []
        if is_remote:
            filters.append('"DSQF7"')  # Remote work filter key
        
        if filters:
            return f"""
            filters: {{
              composite: {{
                filters: [{{
                  keyword: {{
                    field: "attributes",
                    keys: [{', '.join(filters)}]
                  }}
                }}]
              }}
            }}
            """
        return ""
    
    # def _scrape_page(self, search_term: str, location: str, cursor: Optional[str], is_remote: bool) -> tuple[List[JobPost], Optional[str]]:
    #     filters = self._build_filters(is_remote)
    #     query = JOB_SEARCH_QUERY.format(
    #         what=f'what: "{search_term}"' if search_term else "",
    #         location=f'location: {{where: "{location}", radius: 25, radiusUnit: MILES}}' if location else "",
    #         cursor=f'cursor: "{cursor}"' if cursor else "",
    #         filters=filters
    #     )
        
    #     try:
    #         logger.debug(f"Sending request to Indeed API with headers: {json.dumps(self.api_headers, indent=2)}")
    #         logger.debug(f"Query: {query}")
            
    #         response = self.session.post(
    #             self.api_url,
    #             headers=self.api_headers,
    #             json={"query": query},
    #             timeout=10
    #         )
            
    #         # Log response status and headers
    #         logger.debug(f"Response status code: {response.status_code}")
    #         logger.debug(f"Response headers: {json.dumps(dict(response.headers), indent=2)}")
            
    #         response.raise_for_status()
    #         data = response.json()
            
    #         # Log the raw response for debugging
    #         logger.debug(f"Response data: {json.dumps(data, indent=2)}")
            
    #         if 'errors' in data:
    #             logger.error(f"GraphQL errors: {json.dumps(data['errors'], indent=2)}")
    #             return [], None
            
    #         if 'data' not in data:
    #             logger.error("No 'data' field in response")
    #             logger.debug(f"Full response: {json.dumps(data, indent=2)}")
    #             return [], None
                
    #         job_search = data.get('data', {}).get('jobSearch')
    #         if not job_search:
    #             logger.error("No 'jobSearch' field in response data")
    #             return [], None
                
    #         jobs_data = job_search.get('results', [])
    #         new_cursor = job_search.get('pageInfo', {}).get('nextCursor')
            
    #         processed_jobs = []
    #         for job_result in jobs_data:
    #             try:
    #                 job = job_result.get('job')
    #                 if not job:
    #                     logger.warning(f"Missing job data in result: {json.dumps(job_result, indent=2)}")
    #                     continue
                        
    #                 processed_job = self._process_job(job)
    #                 if processed_job:
    #                     processed_jobs.append(processed_job)
    #             except Exception as e:
    #                 logger.error(f"Error processing job: {str(e)}", exc_info=True)
    #                 continue
                    
    #         return processed_jobs, new_cursor
            
    #     except requests.exceptions.RequestException as e:
    #         logger.error(f"Request failed: {str(e)}", exc_info=True)
    #         return [], None
    #     except json.JSONDecodeError as e:
    #         logger.error(f"Failed to parse JSON response: {str(e)}", exc_info=True)
    #         return [], None
    #     except Exception as e:
    #         logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    #         return [], None
    
    def _process_job(self, job: dict) -> Optional[JobPost]:
        try:
            if not job.get('key'):
                logger.warning("Job missing 'key' field")
                return None
                
            job_url = f'https://www.indeed.com/viewjob?jk={job["key"]}'
            if job_url in self.seen_urls:
                logger.debug(f"Skipping duplicate job URL: {job_url}")
                return None
            
            self.seen_urls.add(job_url)
            
            if not job.get('description', {}).get('html'):
                logger.warning(f"Job {job['key']} missing description")
                return None
                
            # Extract compensation
            compensation = self._extract_compensation(job.get("compensation", {}))
            
            # Extract job types
            job_types = self._extract_job_types(job.get("attributes", []))
            
            # Create location object
            location_data = job.get("location", {})
            location = Location(
                city=location_data.get("city"),
                state=location_data.get("admin1Code"),
                country=location_data.get("countryCode")
            )
            
            return JobPost(
                id=f'in-{job["key"]}',
                title=job.get("title", "Unknown Title"),
                description=job["description"]["html"],
                company_name=job.get("employer", {}).get("name"),
                location=location,
                job_type=job_types,
                compensation=compensation,
                date_posted=datetime.fromtimestamp(job["datePublished"] / 1000).strftime("%Y-%m-%d"),
                job_url=job_url,
                is_remote=self._is_remote(job)
            )
            
        except Exception as e:
            logger.error(f"Error processing job data: {str(e)}", exc_info=True)
            logger.debug(f"Problematic job data: {json.dumps(job, indent=2)}")
            return None

    def _extract_compensation(self, compensation: dict) -> Optional[Compensation]:
        if not compensation:
            return None
            
        base_salary = compensation.get("baseSalary") or compensation.get("estimated", {}).get("baseSalary")
        if not base_salary:
            return None
            
        interval = base_salary.get("unitOfWork")
        if not interval:
            return None
            
        try:
            comp_interval = CompensationInterval[interval.upper()]
        except KeyError:
            return None
            
        salary_range = base_salary.get("range", {})
        return Compensation(
            interval=comp_interval,
            min_amount=salary_range.get("min"),
            max_amount=salary_range.get("max"),
            currency=compensation.get("currencyCode", "USD")
        )
    
    def _extract_job_types(self, attributes: list) -> List[JobType]:
        job_types = []
        for attr in attributes:
            label = attr["label"].replace("-", "").replace(" ", "").upper()
            try:
                job_type = JobType[label]
                job_types.append(job_type)
            except KeyError:
                continue
        return job_types
    
    def _is_remote(self, job: dict) -> bool:
        remote_keywords = ["remote", "work from home", "wfh"]
        description = job["description"]["html"].lower()
        location = job["location"]["formatted"]["long"].lower()
        
        return any(
            keyword in description or keyword in location
            for keyword in remote_keywords
        )

# Usage example
if __name__ == "__main__":
    try:
        scraper = IndeedScraper()
        logger.info("Starting job search...")
        jobs = scraper.search_jobs(
            search_term="python developer",
            location="New York, NY",
            results_wanted=10,
            is_remote=True
        )
        
        logger.info(f"Found {len(jobs)} jobs")
        
        for i, job in enumerate(jobs, 1):
            print(f"\nJob {i}:")
            print(f"Title: {job.title}")
            print(f"Company: {job.company_name}")
            print(f"Location: {job.location.city}, {job.location.state}")
            print(f"Remote: {'Yes' if job.is_remote else 'No'}")
            if job.compensation:
                print(f"Compensation: {job.compensation.min_amount}-{job.compensation.max_amount} {job.compensation.currency} ({job.compensation.interval.value})")
            print(f"URL: {job.job_url}")
            
    except Exception as e:
        logger.error(f"Main program error: {str(e)}", exc_info=True)