from zenml import pipeline
from steps import query_data_warehouse , chunk , clean , embed 



@pipeline 
def feature_engineering (user_name:str,wait_for:str|list[str]|None=None)->list[str]:
    
    
    raw_messages = query_data_warehouse.query_data_warehouse([user_name])
    cleaned_documents = clean.clean_messages(raw_messages)
    chunks = chunk.chunk_messages(cleaned_documents, user_name)
    embeded_chunks = embed.embed_and_store(chunks)
    
    return embeded_chunks.invocation_id