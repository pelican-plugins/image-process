Release type: minor

* *Feature:* Add `IMAGE_PROCESS_ADD_CLASS` and `IMAGE_PROCESS_CLASS_PREFIX` settings to control
the `image-process-<transform>` CSS class assignment for processed images.
* *Fix*: Encode URLs in `srcset` when they contain a space or a comma, as those characters have a special meaning in the context of a `srcset` value.
* *Fix:* Improve operations for images with empty margins by using `image.width`/`image.height` instead of `bbox`.
* *Fix:* Preserve HTML indentation when rewriting content.
* *Fix:* Avoid loading images needlessly by only processing images if Pillow can handle them.
* *Tests:* Make tests more resilient to small pixel content differences on ARM vs. Intel architectures.
* *Docs:* Correct cropping transformation values.
