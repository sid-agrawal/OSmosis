
import utils 


def boundary():
    print ("----------------------")

def test_interval_dict():
    d = utils.IntervalDict()

    d.put(1,  5 , "x")
    d.put(10,  14 , "y")
    d.put(100,  500 , "z")
    d.put(500,  600 , "z")
	
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

if __name__ == "__main__":
    test_interval_dict()