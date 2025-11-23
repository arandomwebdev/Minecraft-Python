from math import *

def degSin(number):
    # returns the sine of the number in degrees
    return sin(number * pi / 180)

def degCos(number):
    # returns the cosine of the number in degrees
    return cos(number * pi / 180)

def degTan(number):
    # returns the tangent of the number in degrees
    return tan(number * pi / 180)

def degArctan(number):
    # returns the arc tangent of the number in degrees
    return atan(number * pi / 180)

def degArctan2(number1, number2):
    # returns the arc tangent of the number in degrees
    return atan2(number1 * pi / 180, number2 * pi / 180)