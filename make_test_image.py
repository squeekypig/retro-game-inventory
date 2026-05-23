from PIL import Image, ImageDraw
import os

img = Image.new("RGB", (400, 280), "#c8102e")
draw = ImageDraw.Draw(img)

draw.rectangle([8, 8, 391, 271], outline="#ffd700", width=4)
draw.rectangle([16, 16, 383, 263], outline="#ffd700", width=2)
draw.rectangle([30, 40, 370, 240], fill="white", outline="#cccccc", width=1)
draw.rectangle([30, 40, 370, 90], fill="#e60012")
draw.text((200, 55), "SUPER MARIO WORLD", fill="white", anchor="mm")
draw.text((200, 78), "SUPER NINTENDO ENTERTAINMENT SYSTEM", fill="#ffff00", anchor="mm")
draw.text((200, 120), "Super Mario World", fill="#000000", anchor="mm")
draw.text((200, 150), "Platform: Super Nintendo (SNES)", fill="#333333", anchor="mm")
draw.text((200, 175), "1990 / 1991 Nintendo", fill="#666666", anchor="mm")
draw.rectangle([155, 195, 245, 225], fill="#e60012")
draw.text((200, 210), "Nintendo", fill="white", anchor="mm")

path = os.path.join(os.path.dirname(__file__), "test_cart.jpg")
img.save(path, "JPEG", quality=95)
print(f"Saved: {os.path.getsize(path)} bytes at {path}")
