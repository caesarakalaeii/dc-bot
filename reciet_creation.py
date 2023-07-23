import cv2
import time

DEFAULT_IMAGE_PATH = "paypal_blank.png"

MONTHS_GER = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']

BOLD_LOCATIONS = [((32, 40), 12, (0,  0, 0), "name"),   #Name #1
                  ((935, 41), 12, (0,  0, 0), "amount"),  #Amount #1
                  ((607, 352), 12, (6, 44, 92), "name"),#Name Blue
                  ((935, 484), 12, (0,  0, 0), "amount")  #Amount #4
                  ]

LIGHT_LOCATIONS = [((32,61), 12, (0,  0, 0), "date")] #Date

NORMAL_LOCATIONS = [((32,61), 12, (0,  0, 0), "amount")]

SMALL_LOCATIONS = []

FONT_TYPES = [('paypal_fonts/PayPalSansBig-Regular.woff', BOLD_LOCATIONS),
              ('paypal_fonts/PayPalSansBig-Light.woff', LIGHT_LOCATIONS),
              ('paypal_fonts/PayPalSansSmall-Regular.woff', NORMAL_LOCATIONS),
              ('paypal_fonts/PayPalSansSmall-Medium.woff', SMALL_LOCATIONS)]

def image_creation(amount, name):
    img = cv2.imread(DEFAULT_IMAGE_PATH)
    font = cv2.freetype.createFreeType2()
    
    for type, locations in FONT_TYPES:
        font.loadFontData(fontFileName=type,
                        id=0)
        for values in locations:
            value = assessValue(values, amount, name)
            font.putText(img=img,
                    text=value,
                    org=values[0],
                    fontHeight=values[1],
                    color=values[2],
                    thickness=-1,
                    line_type=cv2.LINE_AA,
                    bottomLeftOrigin=True)
        
   


    return img


def assessValue(values, amount, name):
    if "name" in values:
        return name
    elif "amount" in values:
        return f"{amount} $"
    elif "date" in values:
        t = time.localtime()
        return (f"{t.tm_mday} {MONTHS_GER[t.tm_mon]} {t.tm_year}")
        


if __name__ == '__main__':
    
    cv2.imshow(image_creation(500, "Caesar"))

