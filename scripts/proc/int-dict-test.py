#!/bin/python3

import utils 
from utils import insert_with_split


def boundary():
    print ("----------------------")

def test_interval_dict():
    d = utils.IntervalDict()

    d.put(1,  5 , "x")
    d.put(10,  14 , "y")
    d.put(100,  500 , "z")
	
    boundary()
    print(d)
    boundary()
	

    cases = [
        ((5, 400), [
            ((10, 14), 'y'), 
            ((100, 500), 'z'),
            ]) ,
        ((4,400), [
            ((1, 5), 'x'), 
            ((10, 14), 'y'), 
            ((100, 500), 'z'),
            ]),
        ((4,11), [
            ((1, 5), 'x'), 
            ((10, 14), 'y'),
            ]),
        ((499,500), [
            ((100, 500), 'z')
            ]),
        ((499,501), [
            ((100, 500), 'z'),
            ((500, 600), 'z'),
            ]),
    ]



    for c in cases:
        (start , end), expected = c
        print(f'Checking for [{start},{end})', end ="\t" )
        actual = d.get_interval(start, end)
        if (expected != actual):
            print(f'FAIL {expected} != {actual}')
        else:
            print("PASS")


def display(d):
    boundary()
    print(d)
    boundary()

def test_merge():
    d = utils.IntervalDict()
    d.put(1000,  2000 , "x")
    d.put(3000,  4000 , "x")
    display(d)
	
    insert_with_split(d, 100 , 200, "x")
    display(d)


    insert_with_split(d, 500 , 1500, "x")
    display(d)

    insert_with_split(d, 3500 , 4000, "x")
    display(d)
    
    insert_with_split(d, 3700 , 4500, "x")
    display(d)
    
    insert_with_split(d, 250, 1200, "x")
    display(d)
   
    return

if __name__ == "__main__":
    test_interval_dict()
    test_merge()