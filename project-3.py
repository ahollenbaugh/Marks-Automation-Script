import csv
import re # for regex
import argparse
import sys
import pymongo
import os
from datetime import date
import subprocess
import frametotimecode
import openpyxl
from PIL import Image

def is_consecutive(frame1, frame2):
    return abs(frame1 - frame2) == 1 or frame2 == -1

def range_string(frame1, frame2):
    return str(frame1) + " - " + str(frame2)

# MongoDB

mongo_client = pymongo.MongoClient("mongodb://localhost:27017/")
db = mongo_client["comp467"]
files_collection = db["files"] #1
jobs_collection = db["jobs"] #2

files_documents = [] # store records for the collection called "files" here
jobs_documents = [] # store records for the collection called "jobs" here

# Argparse

parser = argparse.ArgumentParser()

parser.add_argument("--files", dest="workFiles", help="files to process", nargs="+")
parser.add_argument("--verbose", action="store_true", help="show verbose")
parser.add_argument("--xytech", dest="xytech", help="name of xytech file")
parser.add_argument("--output", dest="output", help="csv, xls, or database")
parser.add_argument("--process", dest="video_file", help="name of video file")

args = parser.parse_args()

if args.workFiles is None:
    print("No BL/Flame files selected!")
    sys.exit(2)
else:
    if args.verbose: 
        print("verbose enabled!")
        print(f"workFiles = {args.workFiles}")
        if args.xytech: print(f"xytech = {args.xytech}")
        if args.output: print(f"output = {args.output}")
        if args.video_file: print(f"video_file = {args.video_file}")

print()

# Get name of the person running this script:
current_user = os.getlogin()
if args.verbose: print(f"current_user: {current_user}")

# Get the date the script was run (today's date):
run_date = str(date.today()).replace("-", "")
if args.verbose: print(f"run_date: {run_date}")

# Read and parse data from the Xytech work order:

xytech_directories = list()
with open(args.xytech) as xytech:
    for _ in range(2): # skip first two lines
        next(xytech)
    
    producer = xytech.readline().rstrip() # rstrip() removes \n
    operator = xytech.readline().rstrip()
    job = xytech.readline().rstrip()

    for line in xytech:
        if(re.search("ddnsata", line)):
            xytech_directories.append(line.rstrip())

        if(re.search("Notes:", line)):
            line = next(xytech).rstrip()
            notes = line

# Sanitize input:
producer = producer.split(': ')[1] # WLOG, gets rid of the "Producer: " part
operator = operator.split(': ')[1]
job = job.split(': ')[1]

# Process Baselight (and Flame, if provided) file(s):
frame_dictionary = dict() # key: subdirectory, value(s): frame(s)
for file in args.workFiles:
    if re.search("Baselight", file):
        # First parse Baselight filename:
        filename_info = str(file).strip(".txt").split("_")
        machine = filename_info[0]
        user_on_file = filename_info[1]
        date_of_file = filename_info[2]
        if args.verbose:
            print(f"machine: {machine}")
            print(f"user_on_file: {user_on_file}")
            print(f"date_of_file: {date_of_file}")
        
        # Prepare dictionary/document just in case the user wants to insert into db:
        files_documents.append({"current_user": current_user, 
                                "machine": machine, 
                                "user_on_file": user_on_file, 
                                "date_of_file":date_of_file, 
                                "run_date": run_date})

        # Read and parse data from the Baselight file:
        with open(file) as baselight:
            line_list = baselight.readlines()

            for line in line_list:
                if line != "\n":
                    line = line.rstrip().split("/images1/")[1].split(" ") # separate directory from frames

                    subdirectory = line[0]
                    frames = line[1:len(line)]

                    # if subdirectory doesn't exist in the frame dictionary yet, create a new frame list for it
                    if not bool(frame_dictionary.get(subdirectory)):
                        frame_dictionary[subdirectory] = list()
                    for frame in frames:
                        if frame != '<err>' and frame != '<null>':
                            frame_dictionary[subdirectory].append((user_on_file, date_of_file, int(frame)))
    else:
        if re.search("Flame", file):
            # First parse Flame filename:
            filename_info = str(file).strip(".txt").split("_")
            machine = filename_info[0]
            user_on_file = filename_info[1]
            date_of_file = filename_info[2]
            if args.verbose:
                print(f"machine: {machine}")
                print(f"user_on_file: {user_on_file}")
                print(f"date_of_file: {date_of_file}")
            
            # Prepare dictionary/document just in case the user wants to insert into db:
            files_documents.append({"current_user": current_user, 
                                    "machine": machine, 
                                    "user_on_file": user_on_file, 
                                    "date_of_file":date_of_file, 
                                    "run_date": run_date})

            # Read and parse data from the Flame file:
            with open(file) as flame:
                line_list = flame.readlines()

                for line in line_list:
                    if line != "\n":
                        line = line.rstrip().split("/net/flame-archive ")[1].split(" ") # separate directory from frames

                        subdirectory = line[0]
                        frames = line[1:len(line)]

                        # if subdirectory doesn't exist in the frame dictionary yet, create a new frame list for it
                        if not bool(frame_dictionary.get(subdirectory)):
                            frame_dictionary[subdirectory] = list()
                        for frame in frames:
                            if frame != '<err>' and frame != '<null>':
                                frame_dictionary[subdirectory].append((user_on_file, date_of_file, int(frame)))

# If a Xytech directory contains a Baselight subdirectory, replace with Xytech directory in frame_dictionary:
# basically, make a copy of frame_dictionary, but use the Xytech directories instead of the Baselight ones
final_dict = dict()
for dir in frame_dictionary:
    for xytech_dir in xytech_directories:
        if(re.search(dir, xytech_dir)):
            final_dict[xytech_dir] = frame_dictionary[dir]

# Make a new dict - for each path, for each frame corresponding to that path, new_dict[frame] = path:
final_dict_for_real = dict()
for path in final_dict:
    for tuple in final_dict[path]:
        final_dict_for_real[tuple] = path

# Sort final_dict by key (in this case, the frame part of the tuple):
myKeys = list(final_dict_for_real.keys())
myKeys.sort(key=lambda a: a[2]) # sort each key/tuple by third element (frame) (ugly but it's good enough)
final_dict_for_real = {i: final_dict_for_real[i] for i in myKeys}

# Process video file:

def get_video_duration(file_path):
    command = ['ffmpeg', '-i', file_path]

    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        duration_line = re.search(r"Duration: (.*?),", result.stderr)
        if duration_line:
            duration = duration_line.group(1)
            return duration
        else:
            return "Duration information not found."
    except subprocess.CalledProcessError as e:
        return f"Error: {e}"

duration = get_video_duration(args.video_file)
if args.verbose: print(f"Video Duration: {duration}")

# Convert timecode to total number of frames:

from datetime import datetime

def timecode_to_frames(timecode, frame_rate=24):
  """
  Converts a timecode string to the number of frames at a given frame rate.

  Args:
      timecode: The timecode string in HH:MM:SS.ms format.
      frame_rate: The frame rate (default: 24 fps).

  Returns:
      The number of frames represented by the timecode (int).
  """

  # Parse the timecode string
  try:
    time_obj = datetime.strptime(timecode, "%H:%M:%S.%f")
  except ValueError:
    raise ValueError(f"Invalid timecode format: {timecode}")

  # Calculate total seconds
  total_seconds = time_obj.hour * 3600 + time_obj.minute * 60 + time_obj.second + time_obj.microsecond / 1e6

  # Convert to frames
  num_frames = total_seconds * frame_rate

  return int(num_frames)

num_frames = timecode_to_frames(duration)

if args.verbose: print(f"Number of frames in timecode '{duration}': {num_frames}")


# Get all frame ranges within num_frames:

def get_frame_ranges_within_duration(database_name, collection_name, duration):
    # Connect to MongoDB
    client = pymongo.MongoClient('mongodb://localhost:27017/')
    database = client[database_name]
    collection = database[collection_name]

    # Query for frame ranges within the given duration
    query = {"frames": {"$exists": True}}
    projection = {"_id": 0, "frames": 1}
    cursor = collection.find(query, projection)

    result = []

    for document in cursor:
        frames = document.get("frames")

        if isinstance(frames, int):
            # Handle the case where "frames" is a single number
            if frames <= duration:
                result.append(frames)
        elif isinstance(frames, dict):
            # Handle the case where "frames" is a range of numbers
            start_frame = frames.get("start", 0)
            end_frame = frames.get("end", 0)
            frame_count = end_frame - start_frame + 1

            if frame_count <= duration:
                result.append({"start": start_frame, "end": end_frame})

    return result

result = get_frame_ranges_within_duration("comp467", "jobs", num_frames)

print("Frame ranges within duration:")
if args.verbose: print(result)

def capture_screenshot(input_video, output_image, timecode):
    # Run ffmpeg command to capture screenshot at the specified timecode
    cmd = [
        'ffmpeg',
        '-ss', timecode,
        '-i', input_video,
        '-vframes', '1',
        '-q:v', '2',
        output_image
    ]
    subprocess.run(cmd)

def create_thumbnail(input_image_path, output_thumbnail_path, size=(96, 74)):
    with Image.open(input_image_path) as img:
        img.thumbnail(size)
        img.save(output_thumbnail_path)

# Convert each frame to timecodes so we can grab thumbnails for each frame/frame range:
timecodes_for_thumbnails = []
for frame in result:
    tc = frametotimecode.convert(frame)
    output_image = f'screenshot_{tc.replace(":", "_")}.jpg'
    capture_screenshot(args.video_file, output_image, tc)
    create_thumbnail(output_image, os.path.join(os.getcwd(), f'thumbnail_{tc.replace(":", "_")}.jpg'))
    timecodes_for_thumbnails.append([tc, output_image])

# Upload thumbnails to frame.io:
# token (DO NOT DELETE) = fio-u-KMzOfLxOpmML0XeBZxbhsU5jIleW2UAzf_j2uDmssD8U0uE8B0-1a8iwFe5_kZ85

if args.output == "csv" or "xls":
    # Write results to csv file:
    if args.output == "xls":
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        for timecode in timecodes_for_thumbnails:
            sheet.append(timecode)
        workbook.save('example.xlsx')
    with open('frame_fixes.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Producer", "Operator", "job", "notes"])
        writer.writerow([producer, operator, job, notes])
        writer.writerow([" "])
        writer.writerow(["show location", "frames to fix"])

        # Calculate ranges:
        frame_list = list()
        previous_frame = -1 # to get us started since the first frame won't have a previous frame
        for tuple in final_dict_for_real:
            frame = tuple[2]
            if is_consecutive(frame, previous_frame):
                pass
            else:
                if len(frame_list) == 1: # put this frame on a line by itself
                    writer.writerow([final_dict_for_real[tuple], frame_list[0]])
                else: # print the range
                    writer.writerow([final_dict_for_real[tuple], range_string(frame_list[0], frame_list[-1])])
                frame_list = list() # reset to empty list
            frame_list.append(frame)
            save_previous = previous_frame
            previous_frame = frame # save this frame as the previous so that next time we'll have something to check

        # Handle the last frame:
        if is_consecutive(frame, save_previous):
            writer.writerow([final_dict_for_real[tuple], range_string(save_previous, frame)])
        else:
            writer.writerow([final_dict_for_real[tuple], frame])
elif args.output == "db":
    # Insert into database:
    result1 = files_collection.insert_many(files_documents)

    # Calculate ranges:
    frame_list = list()
    previous_frame = -1 # to get us started since the first frame won't have a previous frame
    for tuple in final_dict_for_real:
        frame = tuple[2]
        if is_consecutive(frame, previous_frame):
            pass
        else:
            if len(frame_list) == 1: # put this frame on a line by itself
                jobs_documents.append({"user_on_file": tuple[0],
                                       "date_of_file": tuple[1],
                                       "location": final_dict_for_real[tuple],
                                       "frames": frame_list[0]})
            else: # print the range
                jobs_documents.append({"user_on_file": tuple[0],
                                       "date_of_file": tuple[1],
                                       "location": final_dict_for_real[tuple],
                                       "frames": range_string(frame_list[0], frame_list[-1])})
            frame_list = list() # reset to empty list
        frame_list.append(frame)
        save_previous = previous_frame
        previous_frame = frame # save this frame as the previous so that next time we'll have something to check

    # Handle the last frame:
    if is_consecutive(frame, save_previous):
        jobs_documents.append({"user_on_file": tuple[0],
                               "date_of_file": tuple[1],
                               "location": final_dict_for_real[tuple],
                               "frames": range_string(save_previous, frame)})
    else:
        jobs_documents.append({"user_on_file": tuple[0],
                               "date_of_file": tuple[1],
                               "location": final_dict_for_real[tuple],
                               "frames": frame})
        
    result2 = jobs_collection.insert_many(jobs_documents)
    print(f"Inserted these documents into the files collection: {result1}")
    print(f"Inserted these documents into the jobs collection: {result2}")







print()
