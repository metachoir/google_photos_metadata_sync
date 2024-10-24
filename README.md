# Google Photos Metadata Sync
A Python script to sync metadata from Google Photos JSON files to their corresponding media files (JPG/MP4). This script helps restore proper creation dates and GPS information after downloading media from Google Photos.

## Features
- Processes both JPG and MP4 files
- Sets file creation time from Google Photos metadata
- Updates EXIF metadata for JPG files
- Adds GPS metadata to media files (when available)
- Preserves original file modification times
- Moves processed JSON files to a separate folder
- Maintains original folder structure for processed JSON files
- Supports recursive directory processing

## Requirements
### Python Packages
```bash
pip install Pillow piexif
```

### Optional Requirements
- `ffmpeg` - Required for MP4 GPS metadata
  - Windows: `winget install ffmpeg` or download from official website
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg` or `sudo yum install ffmpeg`

## Input File Structure
The script expects the following file structure:
```
yourfolder/
├── subfolder1/
│   ├── photo1.jpg
│   ├── photo1.jpg.json
│   ├── video1.mp4
│   └── video1.mp4.json
└── subfolder2/
    ├── photo2.jpg
    └── photo2.jpg.json
```

JSON file example:
```json
{
  "title": "20231001_134635.jpg",
  "creationTime": {
    "timestamp": "1696234400",
    "formatted": "2023. 10. 2. 8:13:20 UTC"
  },
  "photoTakenTime": {
    "timestamp": "1696135595",
    "formatted": "2023. 10. 1. 4:46:35 UTC"
  },
  "geoData": {
    "latitude": 36.8022072,
    "longitude": 126.151219,
    "altitude": 31.0
  }
}
```

## Usage
1. Place the script in the root directory containing your media files
2. Run the script:
```bash
python google_photos_metadata_sync.py
```

The script will:
- Recursively process all JPG and MP4 files in the directory
- Update file creation times using `creationTime` from JSON
- Update EXIF data for JPG files using `photoTakenTime`
- Add GPS data if available in the JSON
- Move successfully processed JSON files to a `processed_json` folder

## Output Structure
After running the script:
```
yourfolder/
├── subfolder1/
│   ├── photo1.jpg        # Updated with metadata
│   ├── video1.mp4        # Updated with metadata
├── subfolder2/
│   └── photo2.jpg        # Updated with metadata
└── processed_json/       # Contains processed JSON files
    ├── subfolder1/
    │   ├── photo1.jpg.json
    │   └── video1.mp4.json
    └── subfolder2/
        └── photo2.jpg.json
```

## Processing Details

### JPG Files
- Updates EXIF date metadata
- Sets file creation time
- Adds GPS coordinates (if available)

### MP4 Files
- Sets file creation time
- Adds GPS metadata (requires ffmpeg)
- Preserves original video quality (no re-encoding)

## Error Handling
- Failed operations are logged to console
- JSON files are only moved if all operations succeed
- Original files are preserved in case of errors
- Backup files are created before modifying MP4 files

## System Support
- Windows: Full support for creation time modification
- Unix/Linux/macOS: Creation time modification depends on filesystem support
- All systems: Full support for EXIF and metadata modifications

## Notes
- Original file modification times are preserved
- The script skips media files without corresponding JSON files
- The script maintains the original folder structure in the `processed_json` directory
- Processed JSON files can be safely deleted after confirming successful metadata updates
