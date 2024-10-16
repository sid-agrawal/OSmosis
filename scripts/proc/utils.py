import bisect
import copy

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
        self.endpoint_list = []
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
        
        insert_idx = bisect.bisect_right(self.endpoint_list, start)
        
        if self.list_len > insert_idx and self.endpoint_list[insert_idx] < end:
            # Interval overlaps another
            print(f'Overlap [{start:16x},{end:16x}]')
            print(self)
            raise ValueError("Overlap interval")
        elif insert_idx > 0 and self.endpoint_list[insert_idx - 1] in self.dict:
            # This start point is already defined
            print(f'Overlap [{start:16x},{end:16x}]')
            print(self)
            raise ValueError("Overlap interval")
        
        # Insert the end point, if needed
        if self.list_len <= insert_idx or self.endpoint_list[insert_idx] != end:
            self.endpoint_list.insert(insert_idx, end)
            self.list_len += 1
        
        # Insert the start point, if needed
        if insert_idx == 0 or self.endpoint_list[insert_idx - 1] != start:
            self.endpoint_list.insert(insert_idx, start)
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
        
        idx = bisect.bisect_right(self.endpoint_list, key)
        
        if idx == 0 or idx >= self.list_len:
            # Index not within any interval
            return (None, None), None
        
        val = self.dict.get(self.endpoint_list[idx - 1])
        
        if val:
            return (self.endpoint_list[idx - 1], self.endpoint_list[idx]), val
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
        
        left_idx = bisect.bisect_left(self.endpoint_list, start + 1)
        right_idx = bisect.bisect_left(self.endpoint_list, end - 1)
        
        results = []
        for i in range(left_idx - 1, right_idx):
            if i < 0 or i >= self.list_len:
                continue
            
            val = self.dict.get(self.endpoint_list[i])
        
            if val:
                results.append(((self.endpoint_list[i], self.endpoint_list[i + 1]), val))

        return results
    
    def split_interval(self, split_at: int) -> any:
        """
        Splits an interval by the given split_at point
        The right split will get a shallow copy of the original value
        
        :param split_at: point at which to split the interval
        :return: the copied value
        """
        
        print(f"Splitting at {split_at:16x}")
        
        idx = bisect.bisect_right(self.endpoint_list, split_at)
        val = self.dict.get(self.endpoint_list[idx - 1])
        
        assert val is not None, f"Can't split a nonexistent interval [{self.endpoint_list[idx - 1]:16x}, {self.endpoint_list[idx]:16x}]"
        assert self.endpoint_list[idx - 1] != split_at and self.endpoint_list[idx] != split_at, "Can't split an interval at the endpoint"
        
        bisect.insort(self.endpoint_list, split_at)
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
            value = self.dict.get(self.endpoint_list[i])
            
            if value:
                items.append(((self.endpoint_list[i],self.endpoint_list[i+1]), value))
    
        return items
    
    def __str__(self):
        lines = []
        for i in range(self.list_len - 1):
            value = self.dict.get(self.endpoint_list[i])
            
            if value:
                lines.append(f'-[{self.endpoint_list[i]:16x},{self.endpoint_list[i+1]:16x}]: {value}')

        return '\n'.join(lines)