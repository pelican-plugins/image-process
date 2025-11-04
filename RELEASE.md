Release type: minor

- Update `ExifImageWidth` & `ExifImageHeight` tags to match dimensions of transformed image when copying EXIF tags
- Copying EXIF tags only updates dimension tags if they existed in the source image
- Add `width` and `height` attributes to `<img>` tags based on processed image’s actual dimensions
- Add Python 3.14 support and require Python 3.10+
