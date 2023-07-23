from PIL import Image
from PIL.ExifTags import TAGS
import os
import glob
import json

def get_meta(filepath):
    dataset = {}
    file_extension = filepath.split('.')[-1].lower()
    if os.path.exists(filepath):
            if file_extension in ['png', 'jpg', 'jpeg', 'jfif']:
                f = Image.open(filepath)
                exifdata = f.getexif()
                for tag_id in exifdata:
                    # get the tag name, instead of human unreadable tag id
                    tag = TAGS.get(tag_id, tag_id)
                    data = exifdata.get(tag_id)
                    # decode bytes 
                    if isinstance(data, bytes):
                        data = data.decode()
                    dataset.update({tag:data})
    else: 
        raise FileNotFoundError
    
    return dataset
    
def scrape_all():
    all_data = {}
    for file_path in glob.glob("./*media/*"):
        all_data.update({file_path:get_meta(file_path)})
    
    
    write_meta(all_data)


def write_meta(all_data):
    with open(os.path.join(os.getcwd(), "scraped_meta.json"), "w") as f:
            f.write(json.dumps(all_data))
            
def detect_web(path):
    """Detects web annotations given an image."""
    from google.cloud import vision

    client = vision.ImageAnnotatorClient()

    with open(path, "rb") as image_file:
        content = image_file.read()

    image = vision.Image(content=content)

    response = client.web_detection(image=image)
    annotations = response.web_detection

    if annotations.best_guess_labels:
        for label in annotations.best_guess_labels:
            print(f"\nBest guess label: {label.label}")

    if annotations.pages_with_matching_images:
        print(
            "\n{} Pages with matching images found:".format(
                len(annotations.pages_with_matching_images)
            )
        )

        for page in annotations.pages_with_matching_images:
            print(f"\n\tPage url   : {page.url}")

            if page.full_matching_images:
                print(
                    "\t{} Full Matches found: ".format(len(page.full_matching_images))
                )

                for image in page.full_matching_images:
                    print(f"\t\tImage url  : {image.url}")

            if page.partial_matching_images:
                print(
                    "\t{} Partial Matches found: ".format(
                        len(page.partial_matching_images)
                    )
                )

                for image in page.partial_matching_images:
                    print(f"\t\tImage url  : {image.url}")

    if annotations.web_entities:
        print("\n{} Web entities found: ".format(len(annotations.web_entities)))

        for entity in annotations.web_entities:
            print(f"\n\tScore      : {entity.score}")
            print(f"\tDescription: {entity.description}")

    if annotations.visually_similar_images:
        print(
            "\n{} visually similar images found:\n".format(
                len(annotations.visually_similar_images)
            )
        )

        for image in annotations.visually_similar_images:
            print(f"\tImage url    : {image.url}")

    if response.error.message:
        raise Exception(
            "{}\nFor more info on error messages, check: "
            "https://cloud.google.com/apis/design/errors".format(response.error.message)
        )

            
            
if __name__ == "__main__":
    scrape_all()