import csv
import logging
import os

import scenedetect
from scenedetect import ContentDetector, SceneManager
from scenedetect.scene_manager import save_images
from scenedetect.video_splitter import split_video_ffmpeg


def split_video_scenes(input_folder: str, output_folder: str, csv_file: str):
    # Ensure output directories exist
    os.makedirs(output_folder, exist_ok=True)
    images_output_folder = os.path.join(output_folder, "images")
    os.makedirs(images_output_folder, exist_ok=True)
    video_output_folder = os.path.join(output_folder, "videos")
    os.makedirs(video_output_folder, exist_ok=True)

    # Check if CSV file exists, create it if not
    if not os.path.exists(csv_file):
        with open(csv_file, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["video_name", "scene_number", "start_time", "end_time"])  # Header row

    # Read the existing CSV to see which videos are already processed
    processed_videos = set()
    with open(csv_file, mode="r") as file:
        reader = csv.reader(file)
        next(reader)  # Skip header
        processed_videos = {row[0] for row in reader}  # Get the set of processed video names

    # Loop through all video files in the input folder
    vids = os.listdir(input_folder)
    logging.info(f"Found {len(vids)} videos")

    for video_file in vids:
        video_name = os.path.splitext(video_file)[0]
        video_path = os.path.join(input_folder, video_file)

        if not video_file.endswith((".mp4", ".avi", ".mov", ".mkv")) or video_name in processed_videos:
            continue  # Skip non-video files or already processed videos

        logging.info(f"Splitting {video_file}...")
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector())
        video = scenedetect.open_video(video_path)
        scene_manager.detect_scenes(video)

        # Get list of detected scenes
        scene_list = scene_manager.get_scene_list()
        logging.info(f"\tdetected {len(scene_list)} scenes")

        # For each scene, extract and save one image, and save the video
        save_images(
            scene_list=scene_list,
            video=video,
            num_images=1,
            image_name_template="$VIDEO_NAME-Scene-$SCENE_NUMBER-$IMAGE_NUMBER",
            output_dir=images_output_folder,
        )
        logging.info(f"\tsaved images")

        split_video_ffmpeg(
            input_video_path=video_path,
            scene_list=scene_list,
            output_dir=video_output_folder,
            output_file_template="$VIDEO_NAME-Scene-$SCENE_NUMBER.mp4",
        )
        logging.info(f"\tsaved videos")

        # Append scene details to CSV
        with open(csv_file, mode="a", newline="") as file:
            writer = csv.writer(file)
            for idx, (start_time, end_time) in enumerate(scene_list):
                writer.writerow([video_name, idx + 1, start_time.get_seconds(), end_time.get_seconds()])

        logging.info(f"\tappended {video_file} to {csv_file}")


split_video_scenes(input_folder="vids", output_folder="vids-split")
