import os
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageChops


def remove_borders(im):
    """Extra background / borders ko remove karta hai."""
    try:
        # Convert to RGB to ensure getpixel and math works fine
        im_rgb = im.convert("RGB")
        # Assume top-left pixel color is the background color (usually solid white/black margin)
        bg_color = im_rgb.getpixel((0, 0))
        bg = Image.new(im_rgb.mode, im_rgb.size, bg_color)
        diff = ImageChops.difference(im_rgb, bg)
        diff = ImageChops.add(diff, diff, 2.0, -100)
        bbox = diff.getbbox()
        if bbox:
            return im.crop(bbox)
        return im
    except Exception:
        # Agar error aaye (eg. animated/weird format), toh original return karo
        return im.convert("RGB")


def start_conversion():
    root = tk.Tk()
    root.withdraw()  # Main window ko hide karne ke liye

    messagebox.showinfo(
        "Step 1", "Apne sabhi 750+ screenshots images ko ek sath select karein."
    )

    # 1. Images select karna
    file_paths = filedialog.askopenfilenames(
        title="Select Images (Screenshots)",
        filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.webp")],
    )

    if not file_paths:
        print("Koi image select nahi ki gayi.")
        return

    messagebox.showinfo(
        "Step 2",
        "Ab choose karein ki PDF kahan save karni hai aur uska kya naam rakhna hai.",
    )

    # 2. Output PDF location select karna
    output_pdf = filedialog.asksaveasfilename(
        title="Save PDF As...",
        defaultextension=".pdf",
        filetypes=[("PDF File", "*.pdf")],
    )

    if not output_pdf:
        print("Save location select nahi ki gayi.")
        return

    print(f"\n======================================")
    print(f"Total {len(file_paths)} images select ki gayi hain.")
    print(f"Processing chalu hai... Please wait!")
    print(f"======================================\n")

    images_list = []

    for i, img_path in enumerate(file_paths):
        try:
            print(f"Processing ({i+1}/{len(file_paths)}): {os.path.basename(img_path)}")
            img = Image.open(img_path)

            # Remove margin / border automatically (taaki clean PDF bane)
            img = remove_borders(img)

            # Resize agar image badi hai (Taaki size aur kam ho jaye quality loose kiye bina)
            # Screenshots normally bade hote hain, unko max 1200 x 1600 me optimize karte hain
            img.thumbnail((1200, 1600), Image.Resampling.LANCZOS)

            # PDF format ke liye image ko RGB me convert karna zaroori hai
            rgb_img = img.convert("RGB")
            images_list.append(rgb_img)

        except Exception as e:
            print(f"Error aayi {os.path.basename(img_path)} me: {e}")

    # 3. PDF Save karna
    if images_list:
        print(
            "\nFinal PDF ban rahi hai, isme 1 se 2 minute lag sakte hain (750+ images ke liye). कृपया प्रतीक्षा करें..."
        )
        # Save first image and append the rest
        # quality=60 (Size ko bahut kam karne ke liye), optimize=True (Faltu data hatane ke liye)
        images_list[0].save(
            output_pdf,
            save_all=True,
            append_images=images_list[1:],
            quality=65,  # Best balanced quality
            optimize=True,
        )
        print("\n✅ Ho gaya! PDF Successfully ban gayi hai.")
        messagebox.showinfo(
            "Success",
            f"Badhai ho! Makkhan ki tarah {len(file_paths)} images ka PDF ban gaya!\n\nSize bhi kam hai.\nFile saved at: {output_pdf}",
        )
    else:
        messagebox.showerror(
            "Error", "Bhai, koi valid images nahi mili ya process nahi ho paayi."
        )


if __name__ == "__main__":
    start_conversion()
