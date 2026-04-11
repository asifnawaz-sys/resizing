import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image
import pandas as pd
import threading

# --- Core Logic ---
def process_images_thread():
    threading.Thread(target=start_process, daemon=True).start()

def start_process():
    input_path = entry_input.get().strip()
    selected_format = format_var.get()
    
    if not input_path or not os.path.exists(input_path):
        messagebox.showerror("Error", "Sahi folder select karen!")
        return

    try:
        width = int(entry_width.get())
        height = int(entry_height.get())
    except ValueError:
        messagebox.showerror("Error", "Width/Height sahi likhen.")
        return

    extensions = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff')
    files = [f for f in os.listdir(input_path) if f.lower().endswith(extensions)]
    total_files = len(files)

    if total_files == 0:
        messagebox.showinfo("No Images", "Is folder mein images nahi hain!")
        return

    btn_run.config(state="disabled")
    label_status.config(text=f"Starting... Total: {total_files}", fg="blue")

    folder_name = os.path.basename(input_path)
    parent_dir = os.path.dirname(input_path)
    output_path = os.path.join(parent_dir, f"{folder_name}-Resized-v1.4")

    if not os.path.exists(output_path):
        os.makedirs(output_path)

    audit_data = []
    processed_count = 0
    
    for filename in files:
        img_full_path = os.path.join(input_path, filename)
        new_filename = filename.rsplit('.', 1)[0] + f".{selected_format.lower()}"
        save_full_path = os.path.join(output_path, new_filename)
        
        try:
            with Image.open(img_full_path) as img:
                # High quality resizing
                resized_img = img.resize((width, height), Image.Resampling.LANCZOS)
                
                if selected_format == "JPG":
                    if resized_img.mode in ("RGBA", "P"):
                        resized_img = resized_img.convert("RGB")
                    quality = 100
                    resized_img.save(save_full_path, "JPEG", quality=quality, optimize=True, subsampling=0)
                    while os.path.getsize(save_full_path) / 1024 > 1000 and quality > 85:
                        quality -= 1
                        resized_img.save(save_full_path, "JPEG", quality=quality, optimize=True, subsampling=0)

                elif selected_format == "PNG":
                    resized_img.save(save_full_path, "PNG", compress_level=3)
                
                elif selected_format == "WebP":
                    quality = 100
                    resized_img.save(save_full_path, "WebP", quality=quality, lossless=False)
                    while os.path.getsize(save_full_path) / 1024 > 1000 and quality > 85:
                        quality -= 1
                        resized_img.save(save_full_path, "WebP", quality=quality)

                processed_count += 1
                label_status.config(text=f"Processing: {processed_count} / {total_files} done...")
                audit_data.append({"File": filename, "Status": "Success"})
        except Exception as e:
            audit_data.append({"File": filename, "Status": "Failed", "Error": str(e)})

    pd.DataFrame(audit_data).to_csv(os.path.join(output_path, "Audit_Report.csv"), index=False)
    label_status.config(text="COMPLETED!", fg="green")
    btn_run.config(state="normal")
    messagebox.showinfo("v1.4 Done", "Process Mukammal ho gaya!")

# --- GUI ---
root = tk.Tk()
root.title("Multi-OS Ultra Resizer v1.4")
root.geometry("500x500")

main_frame = tk.Frame(root, padx=25, pady=20)
main_frame.pack(expand=True, fill="both")

def browse():
    path = filedialog.askdirectory()
    if path:
        entry_input.delete(0, tk.END)
        entry_input.insert(0, path)

tk.Label(main_frame, text="ULTRA RESIZER v1.4", font=("Arial", 16, "bold"), fg="#16a085").pack(pady=10)
tk.Label(main_frame, text="Select Folder:").pack(anchor="w")
entry_input = tk.Entry(main_frame, width=45); entry_input.pack(pady=5)
tk.Button(main_frame, text="Browse", command=browse).pack()

tk.Label(main_frame, text="Format:").pack(anchor="w", pady=(15,0))
format_var = tk.StringVar(value="JPG")
ttk.Combobox(main_frame, textvariable=format_var, values=["JPG", "PNG", "WebP"], state="readonly").pack()

tk.Label(main_frame, text="Resolution (W x H):").pack(anchor="w", pady=(15,0))
dim_frame = tk.Frame(main_frame); dim_frame.pack()
entry_width = tk.Entry(dim_frame, width=10); entry_width.insert(0, "1920"); entry_width.grid(row=0, column=0, padx=5)
entry_height = tk.Entry(dim_frame, width=10); entry_height.insert(0, "1080"); entry_height.grid(row=0, column=1, padx=5)

label_status = tk.Label(main_frame, text="Ready", font=("Arial", 10, "italic"), fg="gray")
label_status.pack(pady=20)

btn_run = tk.Button(main_frame, text="START PROCESSING", bg="#2c3e50", fg="white", font=("Arial", 12, "bold"), pady=10, command=process_images_thread)
btn_run.pack(fill="x")

root.mainloop()
