# Marks Automation Script
## Overview
This script automates four tasks necessary for finding and correcting frame scratches and dirt from scanning:
1. Assist in Color Bay marking shots (normally takes about 4 - 8 hours, and costs about $1500/hour per room, and $100 per operator)
2. Verifying shots in file system (1 - 4 hours, $100/hour operator, $25/hour data op)
3. Producer with a work order with correct files that need fixing (1 hour, $50/hour producer)
4. Edit/VFX receives a CSV with correct files (1 hour, $90/hour specialist)

Running this script daily in a post production facility could therefore save about $3-10k each time.

## How it works
### Project 1
Here's how the first iteration of the script operates:
- Two files are fed into it: a text file containing data exported from Baselight, and another text file containing data from a Xytech work order.
- The script then maps the file system from the local Baselight bay to the facility-wide file system.
- In parsing the data it also discards any errors (e.g., `<null>`, `<err>`).
- Finally, it exports a CSV file with producer/operator/job type/notes at the top, followed by columns corresponding to file location and which frames to fix.
- Frames are presented in the CSV in consecutive order, either individually or grouped into ranges.

Let's illustrate this functionality with some arbitrary example data. Suppose the Baselight file contains this local directory and the botched frames it contains:
`/images1/avengers/reel1/1920x1080 10 11 12 13 19 23 24`

This would get mapped to the facility-wide directory as specified in the Xytech work order:
`/ddnsan2/avengers/reel1/1920x1080`

And the CSV output would look something like this:
|Location|Frames to fix|
|--------|-------------|
|/ddnsan2/avengers/reel1/1920x1080|10-13|
|/ddnsan2/avengers/reel1/1920x1080|19|
|/ddnsan2/avengers/reel1/1920x1080|23-24|

### Project 2
- Scaled-up version of Project 1
- Part of a virtual studio now
- Supports custom input
- Saves records to MongoDB database
    - Collection 1: name of user that ran the script, name of user on file, date on file, date submitted
    - Collection 2: name of user on file, date on file, location, frames
- Accommodates different machines (namely AutoDesk Flame), not just Baselight
- Also accommodates different workflows and users on a per-work order basis

|flag|purpose|example|
|----|-------|-------|
|--files|takes Baselight/Flame files as arguments|`--files Baselight_BBonds_20230326.txt Flame_DFlowers_20230326.txt`
|--xytech|takes Xytech work order file as argument|`--xytech Xytech_20230326.txt`
|--verbose|enables console output|`--verbose`
|--output|takes "csv" or "db" depending on how you want output formatted|`--output csv`

Example run:

`project-2.py --files Baselight_THolland_20230326.txt Flame_DFlowers_20230326.txt --xytech Xytech_20230326.txt --verbose -–output db`

### Project 3
- Upgraded version of Project 2 that displays the actual shots that need to be fixed
- Processes a video file with `--process <video file>`
- Queries database for all ranges that fall within the TRT of said video
- Outputs an XLS with thumbnails for each frame range
- Uploads each shot to frame.io