from flask import Flask, render_template, request, jsonify, session
import uuid,datetime, boto3
# from db_connection import db
from PyPDF2 import PdfReader
import openai
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer   
from sklearn.metrics.pairwise import cosine_similarity

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import  json, os
from flask_cors import CORS
from dotenv import load_dotenv
load_dotenv()

# from scrapping import search_job,scrape_jobs,scrape_multiple_pages,aho
from scrapping import search_and_scrape_jobs

app = Flask(__name__)
CORS(app)
app.secret_key = 'supersecretkey'

# Initialize the sentence transformer model
model = SentenceTransformer('paraphrase-MiniLM-L6-v2')

# Configure AWS S3 client
s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)

BUCKET_NAME = os.getenv('BUCKET_NAME')

# Configure OpenAI API key
openai.api_key = os.getenv('OPENAI_API_KEY')

# Configure CAPTCHA API key
captcha_api_key = os.getenv('CAPTCHA_API_KEY')

def init_driver():
    try:
        chrome_options = Options()
        # Remove duplicate flags
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--enable-unsafe-swiftshader")
        chrome_options.add_argument("--use-gl=swiftshader")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--ignore-gpu-blocklist")
        chrome_options.add_argument("--disable-gpu")
        
        # Use WebDriverManager to automatically manage ChromeDriver
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        return driver
    except Exception as e:
        print(f"Error initializing the WebDriver: {e}")
        return None


@app.route('/')
def index():
    return render_template('index.html')

# @app.route('/render_user_preferences')
# def render_user_preferences():
#     return render_template('user_preferences.html')

# @app.route('/render_login_page')
# def render_login_page():
#     return render_template('login.html')

# @app.route('/render_user_profile')
# def render_user_profile():
#     return render_template('user_profile.html')


# @app.route("/login", methods=["POST"])
# def login():
#     try:
#         if not request.is_json:
#             return jsonify({"error": "Invalid input format, JSON expected"}), 400
#         # Getting email and password from frontend request 
#         data = request.json
#         user_email = data['email']
#         user_password = data['password']

#         # Connect to the database 
#         db.connect()

#         # Find the user by email 
#         find_query = """SELECT user_password FROM [user] WHERE user_email = ?"""
#         db.cursor.execute(find_query, (user_email,))
#         result = db.cursor.fetchone()
        
#         # Check if the user exists 
#         if result:
#             if user_password==result[0]:
#                 # Store the email in the session
#                 session['user_email'] = user_email
#                 return jsonify({"message": "Login Successful"}), 200
#             else:
#                 return jsonify({"message": "Invalid email or password"}), 401
#         else:
#             return jsonify({"message": "User not found"}), 404
#         db.close()
#     except Exception as e:
#         # Handle any errors that occur 
#         return jsonify({"error": str(e)}), 500



# @app.route("/signup", methods=["GET","POST"])
# def signup():
#     try:
#         user_id = str(uuid.uuid4())  
#         user_email = request.json['email']
#         user_password = request.json['password']
#         hashed_password = user_password 
        
#         # Get the current date and time
#         current_date_time = datetime.datetime.now()

#         # Connect to the database
#         db.connect()
        
#         # Insert data into the 'user' table
#         insert_query = """ 
#             INSERT INTO [user] 
#             (user_id, user_email, user_password, user_created_at)
#             VALUES (?, ?, ?, ?)
#         """
#         data = (user_id, user_email, hashed_password, current_date_time)

#         # Execute the insert statement
#         db.cursor.execute(insert_query, data)

#         # Commit the transaction
#         db.commit()
#         return "Account Created", 200

#     except Exception as e:
#         # Handle any errors that occur
#         return jsonify({"error": str(e)}), 500  
    
    
# Function to extract raw text from resume  
def extract_pdf_text(file):
    try:
        reader = PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        print(f"Error extracting PDF text: {str(e)}")
        return None

# Function to make cover letter
def make_cover_letter(text):
    try:
        # Request to OpenAI API for chatbot response
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are the world's most expert Cover letter and Resume writer."},
                {"role": "user", "content": f"""
                    Extracted data from Resume:{text}

                    Take above data of candidate extracted from resume.
                    Write a general cover letter for the candidate.
                    Cover letter should not be specific to a company.
                    Cover letter should be less than 1000 characters.
                    Don't mention any dates.
                    Don't mention any position for which candidate is applying.
                    Make sure to mention all tech and experiences mentioned in the resume.
                    Add new lines where needed.
                    """}
            ]
        )
        # Extract bot's response from the API response
        bot_response = response.choices[0].message.content
        return bot_response
    
    except openai.error.OpenAIError as e:        # Handling OpenAI-specific errors
        return f"An error occurred: {str(e)}"
    except Exception as e:                       # General exception handler for unforeseen errors
        return f"Unexpected error: {str(e)}"

    
# Function to upload file to S3 bucket
def upload_file_to_s3(file, bucket_name, file_key):
    try:
        s3.upload_fileobj(file, bucket_name, file_key)
        print(f"File uploaded to S3 with key: {file_key}")
        return f"https://{bucket_name}.s3.amazonaws.com/{file_key}"
    except Exception as e:
        print(f"Error uploading file to S3: {str(e)}")
        return None    


# Function for Pinecone Setup
def pinecone_setup():
    try:
        # Create an instance of the Pinecone class
        pc = Pinecone(
            api_key="9e402958-62c2-4751-8953-8b3b24c83ee6"  # or replace with your API key directly
        )
        # Check if the index already exists, otherwise create it
        index_name = "rezumatch-index"
        if index_name not in pc.list_indexes().names():
            pc.create_index(
                name=index_name,
                dimension=384,  # Set dimension as per your embedding size
                metric='cosine',  # Use cosine similarity for this task
                spec=ServerlessSpec(
                    cloud='aws',  # or another cloud provider
                    region='us-east-1'  # Adjust region if needed
                )
            )

        # Connect to the index
        index = pc.Index(index_name)
        return index
    except Exception as e:
        print(f"Error during Pinecone setup: {e}")
        return None



# Function to make and upload Resume embedding
def pinecone(user_id, user_cover_letter, index):
    try:
        # Encode the cover letter into an embedding
        embedding = model.encode(user_cover_letter).tolist()
        print(f"Embedding generated, length: {len(embedding)}")
    except Exception as e:
        print(f"Error while encoding the cover letter: {e}")
        return None
    
    try:
        # Upsert the embedding into the Pinecone index
        if index and hasattr(index, 'upsert'):
            index.upsert([(str(user_id), embedding)])
            print("Record successfully upserted")
        else:
            print("Index object is not valid or doesn't have an 'upsert' method")
    except Exception as e:
        print(f"Error while upserting the record: {e}")
        return None

    return None


      
   

# @app.route("/save_user_details", methods=["POST"])
# def save_user_details():
#     try:
#         user_email = session.get('user_email')
#         if not user_email:
#             return jsonify({"error": "User not logged in"}), 401
        
#         # Get id  of the user from database
#         db.cursor.execute("SELECT user_id FROM [user] WHERE user_email = ?", (user_email,))
#         user_id = db.cursor.fetchone()[0]
#         if user_id:
#             print(user_id)
#         else:
#             print("Id not fetched")
            
#         # Get the file from the request
#         if 'file' not in request.files:
#             return jsonify({"error": "No file part"}), 400

#         file = request.files['file']
#         if file.filename == '':
#             return jsonify({"error": "No selected file"}), 400

#         if file and file.filename.endswith('.pdf'):
#             # Extract text from the PDF
#             user_raw_resume_text = extract_pdf_text(file)
#             if not user_raw_resume_text:
#                 return jsonify({"error": "Failed to extract text from PDF"}), 500
#             user_cover_letter = make_cover_letter(user_raw_resume_text)
            
#             print("Cover letter  generated")
#             # Make Embeddings and Upload to Pinecone
#             index = pinecone_setup()
#             pinecone(user_id, user_cover_letter, index)
            
#             print("stored in pinecone")
#             # Rewind file pointer for S3 upload
#             file.seek(0)

#             # Upload the file to S3 using the separate function
#             file_key = f"user_files/{file.filename}"
#             user_resume_link = upload_file_to_s3(file, BUCKET_NAME, file_key)
#             if not user_resume_link:
#                 return jsonify({"error": "Failed to upload file to S3"}), 500

#         user_details = request.form

#         # Connect to the database
#         db.connect()

#         # Check if the user exists in the database by email
#         find_query = "SELECT * FROM [user] WHERE user_email = ?"
#         db.cursor.execute(find_query, (user_email,))
#         existing_user = db.cursor.fetchone()

#         if existing_user:
#             update_query = """
#                 UPDATE [user]
#                 SET user_full_name = ?, user_date_of_birth = ?, user_gender = ?, 
#                 user_phone = ?, user_city = ?, user_country = ?, user_experience = ?, 
#                 user_highest_education = ?, user_industry = ?, user_resume_link = ?, 
#                 user_raw_resume_text = ?
#                 WHERE user_email = ?
#             """
#             db.cursor.execute(update_query, (
#                 user_details['fullname'],
#                 user_details['dob'],
#                 user_details['gender'],
#                 user_details['phone'],
#                 user_details['city'],
#                 user_details['country'],
#                 user_details['experience'],
#                 user_details['education'],
#                 user_details['industry'],
#                 user_resume_link,
#                 user_cover_letter,
#                 user_email
#             ))

#             db.commit()
#             return jsonify({"message": "User details updated successfully"}), 200
#         else:
#             return jsonify({"error": "User not found"}), 404

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500


# Fetch the resume embedding by id
def fetch_resume_embedding(index, user_id):
    result = index.fetch(ids=[user_id])
    
    # Check if the ID exists in the result
    if user_id in result['vectors']:
        embedding = result['vectors'][user_id]['values']
        return embedding
    else:
        raise ValueError(f"Embedding with id {user_id} not found")



@app.route("/application_process", methods=["POST"])
def application_process():
    driver = init_driver()
    if not driver:
        print("WebDriver initialization failed. Exiting program.")
        return jsonify({"error": "WebDriver initialization failed"}), 500

    try:
        # user_email = 'azam@gmail.com'
        # user_email = session.get('user_email')
        # if not user_email:
        #     return jsonify({"error": "User not logged in"}), 401
        # else:
        #     print('user_email:', user_email)
        
        # Check and log the received JSON data
        data = request.get_json()  # Use request.get_json() for consistency

        # Extract jobTitle and location if data exists
        if data:
            jobTitle = data.get('jobTitle')
            if jobTitle and len(jobTitle.split()) > 1:  # Check if it has more than one word
                jobTitle = jobTitle.replace(" ", "+")
                print("jobTitle............",jobTitle)
            location = data.get('location')
        else:
            return jsonify({"error": "No data received"}), 400
        
        # Perform the job search
        real_jobs = search_and_scrape_jobs(jobTitle, location, max_pages=2)
        print("real jobs",real_jobs)
        
        # Save the job to a text file
        with open('real_job_list.json', 'w', encoding='utf-8') as f:
          json.dump(real_jobs, f, indent=4, ensure_ascii=False)
          
        # Get only job descriptions to calculate similarity
        # JDs = []
        # for i in range(len(real_jobs)):
        #     JDs.append(real_jobs[i]['job_description'])
        
        # Get id and cover letter of the user from database
        # db.connect()
        # db.cursor.execute("SELECT user_id,user_raw_resume_text FROM [user] WHERE user_email = ?", (user_email,))
        # result = db.cursor.fetchone()
        # if result:
        #     user_id, user_raw_resume_text = result
        #     print('user_id',user_id)
        # else:
        #     print("Record not fetched.")
        
           
        #  Get the embedding of the user's resume from Pinecone
        # index = pinecone_setup()
        # resume_embedding = fetch_resume_embedding(index,user_id)
        # resume_embedding = [resume_embedding]
        
        
        
        # Create a mapping between job descriptions and their respective job objects (that contain links)
        # description_to_job = {job['job_description']: job for job in real_jobs}

        # Get embeddings and similarity scores
        # job_description_embeddings = model.encode(JDs)
        # similarity_scores = cosine_similarity(resume_embedding, job_description_embeddings).flatten()

        # Zip descriptions with similarity scores and sort
        # job_description_scores = list(zip(JDs, similarity_scores))
        # sorted_job_description_scores = sorted(job_description_scores, key=lambda x: x[1], reverse=True)

        # Now use the description to retrieve the full job details (including link) for output
        # final_job_links = []
        # for job_description, score in sorted_job_description_scores:
        #     # Use the mapping to find the full job details based on the description
        #     job = description_to_job[job_description]
        #     final_job_links.append(job['job_link'])  # Now this works, as job is an object with 'job_link'
        #     print(f"Job Title: {job['job_title']}, Similarity Score: {score}\nJob Link: {job['job_link']}\n")
        
        
        # Save the final job links in a file
        # with open('final_job_links.json', 'w', encoding='utf-8') as f:
        #   json.dump(final_job_links, f, indent=4, ensure_ascii=False)
    
    
    # final_job_links = ["https://pk.indeed.com/rc/clk?jk=d67213d76194f769&from=hp&tk=1icg7qi1rk1d6803&bb=ux3rFVKFkUn7_IlcpM-IGIJpuW7nxtFW4mzcFE0h4yV0AsW4oshEI93JtPOagXibol5TLdg0P_NKdRG32ICdtioTkoKbj1J6r6MmHm2AQLu_tU214z_t5IsB0I8kkp1_KdIjIRTEXTU%3D&xkcb=SoDs67M35QHlkygcO70IbzkdCdPP",
    #                    "https://pk.indeed.com/rc/clk?jk=485742b79ac1f35f&from=hp&tk=1icg7qi1rk1d6803&bb=ux3rFVKFkUkkLgAvPG7zN9xCeNkZmX5nxpzcNsVZ5J_fqkvCCnKhOcgfIwmZsD47VvMoYGhEKcDsRdDR_FzjH3YdKIcNo_7uY05HjBrniYydhj0x-HnWaWHSKgOne5pKRKxuPIDLbJ8%3D&xkcb=SoBi67M35QHlkygcO70PbzkdCdPP"
    #                    ]
        final_job_links = real_jobs               
        return  jsonify({"jobLinks": final_job_links}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
