from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
def setup_driver():
    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.6668.89 Safari/537.36")
    return webdriver.Chrome(options=options)

def scrape_jobs(driver,job_title):
    try:
        # Wait for job cards to load
        wait = WebDriverWait(driver, 10)
        job_cards = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.job_seen_beacon")))
        
        job_links = []
        for card in job_cards:
            try:
                # Updated selector for job links
                link_element = card.find_element(By.CSS_SELECTOR, "h2.jobTitle a")
                jk_id = link_element.get_attribute("data-jk")
                print("jk_id:...............",jk_id)
                job_link = f"https://pk.indeed.com/viewjob?jk={jk_id}&q={job_title}"
                job_links.append(job_link)
            except Exception as e:
                print(f"Error extracting job link: {e}")
                continue
                
        print(f"Found {len(job_links)} job links on this page")
        return job_links
    except Exception as e:
        print(f"Error scraping jobs: {e}")
        return []

def scrape_multiple_pages(driver,job_title, max_pages=3):
    all_job_links = []
    current_page = 1
    
    try:
        while current_page <= max_pages:
            # Scrape current page
            page_links = scrape_jobs(driver,job_title)
            all_job_links.extend(page_links)
            
            # Try to find and click the "Next" button
            try:
                # Updated selector for the "Next" button
                next_button = driver.find_element(By.CSS_SELECTOR, 'a[aria-label="Next Page"]')
                if not next_button.is_enabled():
                    print("Reached last page")
                    break
                next_button.click()
                time.sleep(3)  # Wait for next page to load
                current_page += 1
            except Exception as e:
                print(f"No more pages available: {e}")
                break
                
        return all_job_links
    except Exception as e:
        print(f"Error in pagination: {e}")
        return all_job_links



def extract_job_details(driver, job_links):
    final_jobs = []
    
    for link in job_links:
        try:
            driver.get(link)
            # Longer initial wait for page load
            time.sleep(5)
            
            # Initialize WebDriverWait
            wait = WebDriverWait(driver, 15)
            
            try:
                # Multiple selector attempts for job title
                job_title = None
                title_selector = "h1[class*='jobsearch-JobInfoHeader-title']"
                try:
                    wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, title_selector))
                    )
                    title_element = driver.find_element(By.CSS_SELECTOR, title_selector)

                    job_title = title_element.find_element(By.TAG_NAME, "span").text
                    print("job title:..............",job_title)
                    if job_title:
                        break
                except:
                    continue
                
                # Multiple selector attempts for company name
                company_name = None
                company_selectors = [
                    "div[data-company-name='true']",
                    ".jobsearch-CompanyInfoContainer div[data-testid='company-name']",
                    ".jobsearch-InlineCompanyRating div"
                ]
                for selector in company_selectors:
                    try:
                        company_name = driver.find_element(By.CSS_SELECTOR, selector).text.strip()
                        if company_name:
                            break
                    except:
                        continue
                
                # Multiple selector attempts for location
                location = None
                location_selectors = [
                    "div[data-testid='job-location']",
                    ".jobsearch-JobInfoHeader-subtitle div",
                    ".jobsearch-CompanyInfoContainer div[data-testid='company-location']"
                ]
                for selector in location_selectors:
                    try:
                        location = driver.find_element(By.CSS_SELECTOR, selector).text.strip()
                        if location:
                            break
                    except:
                        continue
                
                # Multiple selector attempts for job description
                description = None
                details_selector = "#jobDescriptionText"
                try:
                    description = ''
                    job_description_div = driver.find_element(By.CSS_SELECTOR, details_selector)
                    child_elements = job_description_div.find_elements(By.XPATH, "./*")
                    for child in enumerate(child_elements, start=1):
                        description += child.text.strip()
                    print("description................",description)
                    if description:
                        break
                except:
                    continue
                
                # Get job type from various possible locations
                job_type = "N/A"
                try:
                    type_elements = driver.find_elements(By.CSS_SELECTOR, 
                        "div.jobsearch-JobDescriptionSection-sectionItem, .jobsearch-JobMetadataHeader-item")
                    
                    for element in type_elements:
                        text = element.text.strip()
                        # Look for common job type indicators
                        if any(indicator in text.lower() for indicator in 
                              ['full-time', 'part-time', 'contract', 'temporary', 'permanent', 'internship']):
                            job_type = text
                            break
                except:
                    pass
                
                # Compile job details
                job_details = {
                    "job_link": link,
                    "job_title": job_title or "Title not found",
                    "company_name": company_name or "Company not found",
                    "job_location": location or "Location not found",
                    "job_type": job_type,
                    "job_description": description or "Description not found"
                }
                print("job_details................\n",job_details)
                # Only append if we got at least the basic details
                if job_title and company_name:
                    final_jobs.append(job_details)
                    print(f"Successfully scraped job: {job_details['job_title']} at {job_details['company_name']}")
                else:
                    print(f"Skipping job due to incomplete data: {link}")
                
            except Exception as e:
                print(f"Error extracting specific job details: {str(e)}")
                continue
                
        except Exception as e:
            print(f"Error accessing job link {link}: {str(e)}")
            continue
        
        # Add a delay between job detail requests to avoid rate limiting
        time.sleep(3)
    
    return final_jobs

def search_and_scrape_jobs(job_title, location, max_pages=2):
    driver = None
    try:
        driver = setup_driver()
        print("Driver setup complete")
        
        # Navigate to Indeed with search parameters
        url = f"https://pk.indeed.com/jobs?q={job_title.replace(' ', '+')}&l={location.replace(' ', '+')}"
        driver.get(url)
        print("Navigated to Indeed")
        
        # Get all job links from multiple pages
        job_links = scrape_multiple_pages(driver,job_title, max_pages)
        print(f"Total job links collected: {len(job_links)}")
        return job_links
    
        # Extract detailed information for each job
        final_jobs = extract_job_details(driver, job_links)
        print(f"Successfully scraped {len(final_jobs)} jobs with details")
        
        return final_jobs
        
    except Exception as e:
        print(f"Error during job search and scraping: {e}")
        return None
        
    finally:
        if driver:
            driver.quit()
            print("Browser closed")

