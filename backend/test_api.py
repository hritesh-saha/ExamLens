import os
import requests
import json

BASE_URL = "http://localhost:8000"
TEST_PDF_PATH = "ExamLens_Work_Division.pdf"

def run_tests():
    print("--- Starting ExamLens API Tests ---\n")

    if not os.path.exists(TEST_PDF_PATH):
        print(f"❌ Error: Dummy PDF '{TEST_PDF_PATH}' not found in the current directory.")
        return

    # 1. Test Ingestion / Upload
    print(f"1. Uploading {TEST_PDF_PATH}...")
    upload_url = f"{BASE_URL}/api/ingest/upload"
    
    with open(TEST_PDF_PATH, "rb") as f:
        files = {"files": (TEST_PDF_PATH, f, "application/pdf")}
        data = {
            "doc_type": "lecture_board",
            "lecture_date": "2026-09-22"
        }
        response = requests.post(upload_url, files=files, data=data)

    if response.status_code != 200:
        print(f"❌ Upload failed: {response.text}")
        return
    
    upload_data = response.json()
    document_id = upload_data["document_id"]
    print(f"✅ Upload successful! Document ID: {document_id}")
    print(f"   Metadata: {json.dumps(upload_data, indent=2)}\n")

    # 2. Test Document Retrieval
    print(f"2. Fetching Document {document_id} metadata...")
    doc_response = requests.get(f"{BASE_URL}/api/documents/{document_id}")
    if doc_response.status_code == 200:
        print("✅ Document metadata retrieved successfully.\n")
    else:
        print(f"❌ Failed to fetch document: {doc_response.text}\n")

    # 3. Test Shared Contract Generation
    print("3. Fetching Shared Page Contract (for Vision/Parsing engines)...")
    contract_response = requests.get(f"{BASE_URL}/api/documents/{document_id}/contract")
    if contract_response.status_code == 200:
        contract_data = contract_response.json()
        print(f"✅ Contract retrieved successfully! Found {len(contract_data)} pages.")
        print(f"   Page 1 Sample: {json.dumps(contract_data[0], indent=2)}\n")
    else:
        print(f"❌ Failed to fetch contract: {contract_response.text}\n")

    # 4. Test Exports (Will return empty or basic structure since we haven't added DB notes yet)
    print("4. Testing Markdown Export Endpoint...")
    export_response = requests.get(f"{BASE_URL}/api/exports/markdown/{document_id}")
    if export_response.status_code in [200, 404]: # 404 is expected if no notes exist yet
        print(f"✅ Export endpoint responded with status: {export_response.status_code}\n")
    else:
        print(f"❌ Export failed: {export_response.text}\n")

    print("--- All tests completed! Check your 'uploads' folder to see the rasterized images and database files. ---")

if __name__ == "__main__":
    run_tests()