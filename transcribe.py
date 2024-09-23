import argparse
import csv
import os
import shutil
import warnings

import scenedetect
import transformers
from moviepy.editor import VideoFileClip
from scenedetect import ContentDetector, SceneManager
from scenedetect.scene_manager import save_images
from scenedetect.video_splitter import split_video_ffmpeg

transformers.logging.set_verbosity_error()
warnings.filterwarnings("ignore", category=FutureWarning)


def video_to_audio(input, output):
    video_clip = VideoFileClip(input)
    audio_clip = video_clip.audio
    audio_clip.write_audiofile(output, verbose=False, logger=None)
    audio_clip.close()
    video_clip.close()


def init_folder(output_folder):
    file = os.path.join(output_folder, "scenes.csv")

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        os.makedirs(os.path.join(output_folder, "videos"))
        with open(file, "w") as f:
            csv_writer = csv.writer(f)
            csv_writer.writerow(["video", "screen_nr", "scene", "image", "start_time", "end_time", "transcription"])
        return []

    with open(file, "r") as f:
        csv_reader = csv.reader(f)
        files = [row[0] for row in csv_reader]
    return files


def scene_generator(input_folder, input_file, output_folder):
    input_path = os.path.join(input_folder, input_file)
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector())
    video = scenedetect.open_video(input_path)
    scene_manager.detect_scenes(video)

    scene_list = scene_manager.get_scene_list(start_in_scene=True)

    file_name, file_ext = os.path.splitext(input_file)
    videos_dir = os.path.join(output_folder, "videos")
    video_dir = os.path.join(videos_dir, file_name)
    scenes_dir = os.path.join(video_dir, "scenes")
    audio_dir = os.path.join(video_dir, "audio")
    images_dir = os.path.join(video_dir, "images")
    if os.path.exists(video_dir):
        shutil.rmtree(video_dir)
    for create_dir in [video_dir, scenes_dir, images_dir, audio_dir]:
        os.makedirs(create_dir)

    save_images(
        scene_list=scene_list,
        video=video,
        num_images=1,
        output_dir=images_dir,
        image_name_template="$SCENE_NUMBER",
    )

    split_video_ffmpeg(
        input_video_path=input_path,
        scene_list=scene_list,
        output_dir=scenes_dir,
        output_file_template=f"$SCENE_NUMBER{file_ext}",
    )

    for i, (start_time, end_time) in enumerate(scene_list):
        scene_nr = str(i + 1).zfill(3)
        scene_file = f"{scene_nr}{file_ext}"
        image_file = f"{scene_nr}.jpg"
        audio_file = f"{scene_nr}.mp3"
        scene_path = os.path.join(scenes_dir, scene_file)
        image_path = os.path.join(images_dir, image_file)
        audio_path = os.path.join(audio_dir, audio_file)

        video_to_audio(scene_path, audio_path)

        scene = {
            "video": input_file,
            "scene_nr": scene_nr,
            "scene": scene_path,
            "image": image_path,
            "audio": audio_path,
            "start_time": start_time,
            "end_time": end_time,
        }
        yield scene


def main(output_folder, input_folder, input_files):
    n = len(input_files)
    print(f"Transcribing {n} files")

    transcriber = transformers.pipeline("automatic-speech-recognition", "distil-whisper/distil-large-v3")
    output_csv = os.path.join(output_folder, "scenes.csv")
    with open(output_csv, "a") as f:
        csv_writer = csv.writer(f)
        for i, input_file in enumerate(input_files):
            print(f"- {input_file}")

            # separating the write, because if one scene has been written to CSV,
            # we skip the whole video if the script is run again
            rows = []

            for scene in scene_generator(input_folder, input_file, output_folder):
                res = transcriber(scene["audio"])
                scene["transcription"] = res.get("text", "NO TRANSCRIPTION FOUND")
                rows.append(
                    [
                        scene["video"],
                        scene["scene_nr"],
                        scene["scene"],
                        scene["image"],
                        scene["start_time"],
                        scene["end_time"],
                        scene["transcription"],
                    ]
                )

            for row in rows:
                csv_writer.writerow(row)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert videos to audio")
    parser.add_argument("folder", type=str, help="Folder containing video files")
    parser.add_argument("--output", type=str, help="Output folder", default="transcribed_scenes")

    args = parser.parse_args()

    done = init_folder(args.output)
    todo = []
    for file in os.listdir(args.folder):
        if not file.endswith((".mp4", ".avi", ".mov", ".mkv")):
            continue
        if file in done:
            continue
        todo.append(file)

    main(args.output, args.folder, todo)
