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