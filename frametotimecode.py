# Converts frame count to timecode, assuming 24 frames per second.
FPS = 24
    
def pad_zero(value):
    value = str(value)
    if int(value) < 10:
        return "0" + value
    return value
   
def pad_timecode(value_list):
    padded_list = []
    for value in value_list:
        value = pad_zero(value)
        padded_list.append(value)
    return padded_list

def convert(frames):
    frames = int(frames)
    seconds = int(frames / FPS)
    frames = frames - (seconds * FPS)

    minutes = hours = 0
    if seconds >= 60:
        minutes = int(seconds / 60)
        seconds -= (minutes * 60)
        if minutes >= 60:
            hours = int(minutes / 60)
            minutes -= (hours * 60)

    timecode_list = [hours, minutes, seconds, frames]
    timecode_list = pad_timecode(timecode_list)

    return f"{timecode_list[0]}:{timecode_list[1]}:{timecode_list[2]}:{timecode_list[3]}"