PACKAGER_PATH = src//tools/Package-All.py
BUILD_PATH = build
ZIP_SRC_PATH = src//out//LinuxPatchExtension.zip
MANIFEST_PATH = src//extension//src//manifest.xml
NAME = $$(grep -Pom1 "(?<=<Type>)[^<]+" $(MANIFEST_PATH))
VERSION = $$(grep -Pom1 "(?<=<Version>)[^<]+" $(MANIFEST_PATH))

build: clean make-extension
	@echo "Moving '$(NAME).zip' to '$(BUILD_PATH)/$(NAME)-$(VERSION)'"
	@mkdir -p $(BUILD_PATH)//$(NAME)-$(VERSION)
	@mv $(ZIP_SRC_PATH) $(BUILD_PATH)//$(NAME)-$(VERSION)

make-extension: 
	@echo "Building '$(NAME).zip' ..." 
	@python $(PACKAGER_PATH) && wait
	
clean:
	rm -rf build

.PHONY: clean make-extension build