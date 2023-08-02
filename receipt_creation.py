import io
from PIL import Image, ImageDraw, ImageFont
import time

import discord

DEFAULT_IMAGE_PATH = "paypal_blank.png"

MONTHS_GER = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']

BOLD_LOCATIONS = [((83,34), 20, (0,  0, 0, 255), "name", "lb"),   #Name #1
                  ((984,38), 25, (0,  0, 0, 255), "amount", "rb"),  #Amount #1
                  ((609, 349), 20, (16, 114, 235, 255), "name", "lb"),#Name Blue
                  (( 982, 483), 25, (0,  0, 0, 255), "amount", "rb")  #Amount #4
                  ]

LIGHT_LOCATIONS = [((82,58), 15, (0,  0, 0, 255), "date", "lb")] #Date

NORMAL_LOCATIONS = [((982, 434), 25, (0,  0, 0, 255), "amount", "rb"),
                    ((707,433), 20, (0,0,0,255), "name", "lb"),
                    ((459,354), 25, (0,0,0,255), "amount", "rb")
                    ]

SMALL_LOCATIONS = []

FONT_TYPES = [('paypal_fonts/PayPalSansBig-Regular.woff', BOLD_LOCATIONS),
              ('paypal_fonts/PayPalSansBig-Light.woff', LIGHT_LOCATIONS),
              ('paypal_fonts/PayPalSansSmall-Regular.woff', NORMAL_LOCATIONS),
              ('paypal_fonts/PayPalSansSmall-Medium.woff', SMALL_LOCATIONS)]

def image_creation(amount, name):
    file_size = 0
    while file_size == 0:
        with Image.open(DEFAULT_IMAGE_PATH).convert("RGBA") as img:
            txt = Image.new("RGBA", img.size, (255, 255, 255, 0))
            d = ImageDraw.Draw(txt)
            for type, locations in FONT_TYPES:
                for values in locations:
                    font = ImageFont.truetype(type,values[1])
                    value = assessValue(values, amount, name)
                    if values[2] == (16, 114, 235, 255):
                        value += " schreiben"
                    elif values[0] == (984,38):
                        value = f"- {value}"
                    d.text(values[0],value, font=font,fill = values[2], anchor=values[4])
                    
        out = Image.alpha_composite(img, txt)
        image_stream = io.BytesIO()
            
        # Save the image to the BytesIO object in PNG format
        out.save(image_stream, format='PNG')
        
        # Reset the stream position to the beginning
        image_stream.seek(0)
        
        file = discord.File(fp=image_stream, filename='receipt.png')
        file_size=file.fp.__sizeof__()
    return file
    


def assessValue(values, amount, name):
    if "name" in values:
        return name
    elif "amount" in values:
        return f"{amount},00 $"
    elif "date" in values:
        t = time.localtime()
        return (f"{t.tm_mday} {MONTHS_GER[t.tm_mon -1]} {t.tm_year}")
        


if __name__ == '__main__':
    image_creation(500, "Caesar")


