import json


def retrieve_docs_by_fen(docs_path, fen: str):
    with open(docs_path) as f:
        doc_jsons = f.read().split("\n")
    doc_jsons = [json.loads(json_str) for json_str in doc_jsons]
    retrieved_docs = []
    for doc in doc_jsons:
        if doc["metadata"]["fen"] == fen:
            retrieved_docs.append(doc)
    return retrieved_docs
