import os
from PIL import Image

# Paths
src_path = r"c:/Users/trix4/.gemini/antigravity-ide/scratch/proofmint/apps/web/public/mint_proofmark_logo.png"
output_dir = r"c:/Users/trix4/.gemini/antigravity-ide/scratch/proofmint/apps/web/public"

im = Image.open(src_path).convert("RGBA")
width, height = im.size
# Assume emblem is left square region (height x height)
emblem = im.crop((0, 0, height, height))
# Save PNG for reference
png_path = os.path.join(output_dir, "favicon-p.png")
emblem.save(png_path)
# Generate multi-size ICO (32,48,64,128)
ios_path = os.path.join(output_dir, "favicon.ico")
emblem.save(ios_path, format="ICO", sizes=[(32,32), (48,48), (64,64), (128,128)])
print('Created', png_path, 'and', ios_path)
