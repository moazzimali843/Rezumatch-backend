from flask import Flask, request, jsonify
from flask_cors import CORS
import csv
from jobspy import scrape_jobs

app = Flask(__name__)

CORS(app)


@app.route('/scrape-jobs', methods=['POST'])
def scrape_jobs_endpoint():
    data = request.json
    search_term = data.get('search_term')
    location = data.get('location')
    country = data.get('country')

    if not search_term or not location or not country:
        return jsonify({"error": "Missing search term or location or country"}), 400

    try:
        jobs = scrape_jobs(
            site_name=["indeed"],
            search_term=search_term,
            google_search_term=f"{search_term} jobs in {location}",
            location=location,
            results_wanted=200,
            easy_apply=True,
            country_indeed=country,
        )
        # Ensure job_url is a list of strings, not a pandas Series
        job_links = jobs.job_url.tolist()  # Convert to list of job URLs

        print(job_links)  # Optionally print job links for debugging

        # Save the job listings to a CSV file
        jobs.to_csv("jobs_pakistan.csv", quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)

        # Return the list of job links as part of the JSON response
        return jsonify({"message": f"Found {len(job_links)} jobs", "jobLinks": job_links}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
