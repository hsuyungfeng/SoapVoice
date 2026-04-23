#!/bin/bash
# USB Copy Command for SoapVoice
# Run this script to copy project to USB

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  SoapVoice USB Copy Script                                     ║"
echo "║  Transfers project from Linux to USB (9.3 GB)                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Check USB
echo "STEP 1: Checking USB mount location..."
mount | grep media
echo ""
echo "⚠️  IMPORTANT: Copy the mount path from above (e.g., /media/hsu/USB_DRIVE)"
echo ""

read -p "Enter USB mount path (e.g., /media/hsu/USB_DRIVE): " USB_PATH

# Validate path
if [ ! -d "$USB_PATH" ]; then
    echo "❌ ERROR: Path '$USB_PATH' does not exist!"
    echo "Please insert USB drive and try again."
    exit 1
fi

echo "✅ USB path confirmed: $USB_PATH"
echo ""

# Step 2: Copy project
echo "STEP 2: Copying SoapVoice project to USB..."
echo "This will take 5-10 minutes (9.3 GB)..."
echo ""

rsync -av --progress ~/Desktop/SoapVoice "$USB_PATH/"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Copy completed successfully!"
else
    echo ""
    echo "❌ Copy failed! Check errors above."
    exit 1
fi

# Step 3: Verify
echo ""
echo "STEP 3: Verifying copy..."
echo ""
ls -lh "$USB_PATH/SoapVoice/"
echo ""
du -sh "$USB_PATH/SoapVoice/"
echo ""

# Step 4: Sync
echo "STEP 4: Syncing to USB (important!)..."
sync
echo "✅ Sync complete"
echo ""

# Step 5: Eject
echo "STEP 5: Safely ejecting USB..."
umount "$USB_PATH"
if [ $? -eq 0 ]; then
    echo "✅ USB safely ejected!"
    echo ""
    echo "You can now remove the USB drive and transfer to Windows machine."
else
    echo "⚠️  Could not automatically eject. Please eject manually in file manager:"
    echo "   Right-click USB → Eject"
fi

echo ""
echo "═════════════════════════════════════════════════════════════════"
echo "✨ All done! USB is ready for Windows machine."
echo "═════════════════════════════════════════════════════════════════"
