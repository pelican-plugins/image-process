Release type: patch

*bug*: Wait before we actually need to process the image for checking if Pillow can handle it; this avoids loading the image needlessly. See [Pull Request #72](https://github.com/pelican-plugins/image-process/pull/72). Thanks [Patrick Fournier](https://github.com/patrickfournier)!
*bug*: Fix incorrect cropping transformation documentation. See [Pull Request #77](https://github.com/pelican-plugins/image-process/pull/77). Thanks [Lance Goyke](https://github.com/lancegoyke)!
*bug*: Support `lxml` v5. See [Issue #80](https://github.com/pelican-plugins/image-process/issues/80). Thanks [MinchinWeb](https://github.com/MinchinWeb)!
*support*: Update pre-commit hook versions.
