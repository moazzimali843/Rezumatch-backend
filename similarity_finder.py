import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
model = SentenceTransformer('paraphrase-MiniLM-L6-v2')

def similarity_function(df, userJobTitle):
    columns_to_check = ['job_url', 'job_url_direct', 'title', 'description']
    df_cleaned = df[df[columns_to_check].notna().all(axis=1)].copy()
    user_input = userJobTitle
    user_input_embedding = model.encode([user_input])
    titles_embeddings = model.encode(df_cleaned['title'].tolist())
    similarity_scores = cosine_similarity(user_input_embedding, titles_embeddings).flatten()
    df_cleaned['similarity_score'] = similarity_scores
    df_sorted = df_cleaned.sort_values(by='similarity_score', ascending=False)
    job_urls = df_sorted['job_url'].tolist()
    return job_urls[:20] if len(job_urls) > 20 else job_urls