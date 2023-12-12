import csv
import re # for regex
import argparse
import sys
import pymongo
import os
from datetime import date

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
parser.add_argument("--output", dest="output", help="csv or database")

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

if args.output == "csv":
    # Write results to csv file:
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
else:
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
