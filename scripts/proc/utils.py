import bisect
import copy
import traceback
import os
import filecmp
import subprocess

### UTILITY CLASSES ###

class EasyDict():
    """
    Dict where entries can be accessed with dot notation
    """
    
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __getattr__(self, name):
        return self.__dict__.get(name)
    
    def __setattr__(self, name, val):
        self.__dict__[name] = val
    
    def __delattr__(self, name):
        del self.__dict__[name]
 
    def __str__(self):
        return self.__dict__.__str__()
    
    def __repr__(self):
        return self.__dict__.__str__()
    
    def values(self):
        return self.__dict__.values()

class IntervalDict():
    """
    Dict where a range of numbers map to a value 
    
    Supports put, get, and split (not delete)
    """
    
    def __init__(self):
        self.markers = [] # This is both start and endpoints
        self.dict = {}
        self.list_len = 0
    
    def put(self, start: int, end: int, value: any):
        """
        Add a value to the dictionary for an interval key
        This will fail if it overlaps an existing interval in the dict
        Assumes closed start points and open end points
        
        :param start: start of the interval key
        :param end: end of the interval key
        :param value: value to add to the dict for the specified interval
        """
        
        insert_idx = bisect.bisect_right(self.markers, start)

        # The previous marker is a start point so you are clearly in the middle.
        if insert_idx > 0 and self.markers[insert_idx - 1] in self.dict:
            print(f'----Overlap_B : = Idx: {insert_idx} Marker_At_Index {self.markers[insert_idx]:16x}    [{start:16x},{end:16x}]')
            raise ValueError("Overlap Start interval")
        
        # Prev is not a start. So just check if your end will trample over the next interval
        if self.list_len > insert_idx and self.markers[insert_idx] < end:
            print(f'----Overlap_A : = Idx: {insert_idx} Marker_At_Index '
                  f'{self.markers[insert_idx]:16x}    '
                  f'{self.markers[insert_idx+1]:16x}    '
                  f'[{start:16x},{end:16x}]')
            raise ValueError("Overlap End interval")

        # Insert the end point, if needed
        if self.list_len <= insert_idx or self.markers[insert_idx] != end:
            self.markers.insert(insert_idx, end)
            self.list_len += 1
        
        # Insert the start point, if needed
        if insert_idx == 0 or self.markers[insert_idx - 1] != start:
            self.markers.insert(insert_idx, start)
            self.list_len += 1
            
        # Insert the value to the dict
        self.dict[start] = value
        
    def get(self, key: int) -> tuple[tuple[int,int], any]:
        """
        Get the value for the interval containing the key
        
        :param key: the value to search for in intervals
        :return: a tuple of the interval and value, ((interval_start, interval_end), val)
                 or, if the key is not in any interval, ((None, None), None)
        """
        
        idx = bisect.bisect_right(self.markers, key)
        
        if idx == 0 or idx >= self.list_len:
            # Index not within any interval
            return (None, None), None
        
        val = self.dict.get(self.markers[idx - 1])
        
        if val:
            return (self.markers[idx - 1], self.markers[idx]), val
        else:
            return (None, None), None
        
    def get_interval(self, start: int, end: int) -> list[tuple[tuple[int,int], any]]:
        """
        Get all intervals and values contained within the specified interval
        
        :param start: start of the range to search for in intervals
        :param end: end of the range to search for in intervals
        :return: a list of tuples of the interval and value, ((interval_start, interval_end), val)
                 or, if the range does not contain any interval, an empty list
        """
        
        left_idx = bisect.bisect_left(self.markers, start + 1)
        right_idx = bisect.bisect_right(self.markers, end - 1)
        
        results = []
        for i in range(left_idx - 1, right_idx):
            if i < 0 or i >= self.list_len:
                continue
            
            val = self.dict.get(self.markers[i])
        
            if val:
                results.append(((self.markers[i], self.markers[i + 1]), val))

        return results
    
    def split_interval(self, split_at: int) -> any:
        """
        Splits an interval by the given split_at point
        The right split will get a shallow copy of the original value
        
        :param split_at: point at which to split the interval
        :return: the copied value
        """
        
        
        idx = bisect.bisect_right(self.markers, split_at)
        val = self.dict.get(self.markers[idx - 1])
        
        assert val is not None, f"Can't split a nonexistent interval [{self.markers[idx - 1]:16x}, {self.markers[idx]:16x}]"
        assert self.markers[idx - 1] != split_at and self.markers[idx] != split_at, "Can't split an interval at the endpoint"
        
        bisect.insort(self.markers, split_at)
        self.list_len += 1
        val_copy = copy.copy(val)
        self.dict[split_at] = val_copy
        
        return val_copy
    
    def items(self) -> list[tuple[tuple[int,int], any]]:
        """
        Get a list of all the intervals and values in the dict
        """
        items = []
        
        for i in range(self.list_len - 1):
            value = self.dict.get(self.markers[i])
            
            if value:
                items.append(((self.markers[i],self.markers[i+1]), value))
    
        return items
    
    def __str__(self):
        lines = []
        for i in range(self.list_len - 1):
            value = self.dict.get(self.markers[i])
            
            if value:
                #lines.append(f'-[{self.endpoint_list[i]:16x},{self.endpoint_list[i+1]:16x}]: {value}')
                lines.append(f'-[{self.markers[i]},{self.markers[i+1]}]: {value}')

        return '\n'.join(lines)


def insert_with_split(d: IntervalDict, start ,end, info: any):
    """
    Add new entry {(start, end), info} and if it overlaps with other entry(ies), 
    split them accordingly.
    """
    
    overlaps = d.get_interval(start, end)
    for o in overlaps:
        (existing_start, existing_end) , info = o


        # Is there more of this new interval remaining.
        while start < end:
            if start < existing_start:
                d.put(start, existing_start , info)
            elif existing_start < start:
                d.split_interval(start)
            # else when equal, do nothing.

            # How much to increase start depends on 
            # how whether the new interval's end comes sooner
            # or the exiting interval's end comes sooner. 
            if existing_end <= end:
                start = existing_end
            else:
                d.split_interval(end)
                start = end
            
            # Done with this existing interval
            if start >= existing_end:
                break
    
    # Left over interval
    if start < end:
        d.put(start, end , info)

#     ```
#      Lies outside
#      Get_intervals should return zero here.
#      No Split needed
#                                     <------Existing---Region----->
#                                                                       <-----New---Region--->
#        <-----New---Region--->


#      A new entry can overlap with
#      Types of Split needed when overlaps
#      Overlap with start
#                <------Existing---Region----->    |  <-----next existing start--->
#                                   |         |    |    |
#       1.a>   <-----New---Region--->         |    |    |   Less Than end    : 1 insert and 1 split
#       1.b>   <-----New---Region------------>     |    |   Equal to End     : 1 insert and 0 split
#       1.c>   <-----New---Region------------------>    |   Greater than end : 2 inserts and 0 splits
#       1.d>   <-----New---Region---------------------->    Greater than end : 2 inserts and 0 splits

#      Overlap with End
#               |   <------Existing---Region----->
#               |   |                  |
#       2.a>    |   |                  <-----New---Region--->    Less than end    : 1 insert and 1 split
#       2.b>    |   |<-----------------------New---Region--->    Equal to end     : 1 inser and 0 split
#       2.c>    |<---------New---Region--------------------->    Greater than end : 2 insert and 0 split

#      Old Lies within new:
#       3.a>                                  <-----Existing---Region--->      # 1.c or 2.c
#      .                                  <---------------New---Region------->


#      New lies Within Old
#                                   <-------------Existing---Region----->
#       4.a>                                  <-----New---Region--->      # 1.a and 2.a combined


#      Double Over Lap
#                <------Existing---Region----->    |
#                                   |         |    |
#       5.a>   <-----New---Region--->         |    |    Less Than end    : 1 insert and 1 split
#       5.b>   <-----New---Region------------>     |    Equal to End     : 1 insert and 0 split
#       5.c>   <-----New---Region------------------>    Greater than end : 2 inserts and 0 splits

#      Split if this PMR extends over an entire older PMR
# ```


def sizeof_fmt(num, suffix="B"):
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"

# 00001000-0009fbff : System RAM
# 00100000-07fdcfff : System RAM

# >>> utils.sizeof_fmt(y)
# '635.0KiB'
# >>> y = -0x00100000 + 0x07fdcfff
# >>> utils.sizeof_fmt(y)
# '126.9MiB'

# gpa2hpa 0x1000
# gpa2hpa 0x2000
# gpa2hpa 0x3000
# gpa2hpa 0x4000

def compare_directories(dir1, dir2, file_extension, exceptions) -> bool:
    # Get list of files in both directories with the specified extension
    files_dir1 = {f for f in os.listdir(dir1) if f.endswith(file_extension)}
    files_dir2 = {f for f in os.listdir(dir2) if f.endswith(file_extension)}

    # Check for files that are only in one of the directories
    only_in_dir1 = files_dir1 - files_dir2
    only_in_dir2 = files_dir2 - files_dir1

    if only_in_dir1:
        print(f"Files only in {dir1}: {only_in_dir1}")
        return False
    if only_in_dir2:
        print(f"Files only in {dir2}: {only_in_dir2}")
        return False

    # Compare common files
    common_files = files_dir1 & files_dir2
    for file_name in common_files:
        if file_name in exceptions:
            continue
        file1 = os.path.join(dir1, file_name)
        file2 = os.path.join(dir2, file_name)
        if not filecmp.cmp(file1, file2, shallow=False):
            print(f"Files {file1} and {file2} are different")
            return False
    
    return True


def is_root():
    return os.geteuid() == 0


def docker_cmd(
    cmd: str, container_name: str, exec_cmd: str = "", image: str = "", debug: bool = False
):

    assert container_name != ""

    match cmd:
        case "run":
            assert image != ""
            command = [
                "docker",
                "run",
                "--rm",
                "-id", # Detach
                "--name",
                container_name,
                image,
                exec_cmd,
            ]
        case "rm":
            command = [
                'docker',
                'rm',
                '-f',
                container_name
            ]
        case "inspect":
            command = [
                'docker',
                'inspect',
                container_name
            ]
        case "exec":
            assert exec_cmd != ""
            command = [
                'docker',
                'exec',
                container_name,
                'sh',
                '-c',
                exec_cmd
            ]
        case "restart":
            command = [ 'docker', 
                       'restart', 
                       container_name
                       ]
        case  _: 
            raise ValueError("Invalid Qemu Monitor Command")

    print (f"RUNNING: {command}")
    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if debug:
            print("Command output:", result.stdout)
        print("SUCCESS")
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error occurred: {e.stderr}")


def run(cmds: list[str], debug:bool = False):
    print (f"RUNNING: {cmds}")
    try:
        result = subprocess.run(cmds)
        if debug:
            print("Command output:", result.stdout)
        print("SUCCESS")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error occurred: {e.stderr}")
