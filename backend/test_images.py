import os
import requests
import glob
import shutil
import time

BASE_URL = "http://localhost:8000"
# Standard WSL path for Windows 11 Screenshots folder
SCREENSHOTS_DIR = "/mnt/c/Users/Hritesh/Pictures/Screenshots"
UPLOAD_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")

def test_image_to_pdf():
    print("--- Testing Image-to-PDF Ingestion ---\n")

    # 1. Grab the 3 oldest images from Screenshots
    search_path = os.path.join(SCREENSHOTS_DIR, "*.*")
    all_files = [f for f in glob.glob(search_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    all_files.sort(key=os.path.getmtime)
    
    test_images = all_files[:3]
    if len(test_images) < 3:
        print(f"❌ Not enough images found in {SCREENSHOTS_DIR}. Please take a few screenshots and try again.")
        return

    print(f"Found 3 images to upload:\n" + "\n".join([f" - {os.path.basename(img)}" for img in test_images]) + "\n")

    # 2. Prepare the multipart/form-data payload
    files = []
    file_handles = []
    for img_path in test_images:
        f = open(img_path, 'rb')
        file_handles.append(f)
        files.append(('files', (os.path.basename(img_path), f, 'image/png')))

    data = {
        "doc_type": "lecture_board",
        "lecture_date": "2026-09-22"
    }

    # 3. Hit the API
    print("Uploading images and generating PDF...")
    upload_url = f"{BASE_URL}/api/ingest/upload"
    response = requests.post(upload_url, files=files, data=data)

    # Close file handles to avoid locking issues
    for f in file_handles:
        f.close()

    # 4. Evaluate Response
    if response.status_code == 200:
        resp_data = response.json()
        doc_id = resp_data['document_id']
        print(f"✅ Upload successful! Document ID: {doc_id}")
        
        # Verify the file was created in the database
        doc_response = requests.get(f"{BASE_URL}/api/documents/{doc_id}")
        if doc_response.status_code == 200:
            doc_info = doc_response.json()
            pdf_path = doc_info['file_path']
            print(f"✅ System generated merged PDF at: {pdf_path}")
            
            # 5. Clean up / Delete the generated folder
            print("\nCleaning up...")
            time.sleep(1) # Brief pause to ensure files are released
            folder_to_delete = os.path.dirname(pdf_path)
            if os.path.exists(folder_to_delete):
                shutil.rmtree(folder_to_delete)
                print(f"✅ Deleted generated folder: {folder_to_delete}")
            else:
                print("⚠️ Could not locate folder for deletion.")
    else:
        print(f"❌ Upload failed: {response.text}")

    print("\n--- Image Test Complete ---")

if __name__ == "__main__":
    test_image_to_pdf()