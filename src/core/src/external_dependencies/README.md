
# Azure Linux VM Patch Extension - External Dependencies

Any projects or code that is obtained from external repositories are referenced from this folder, and details of each of them are listed below.

# 1. Distro - an OS platform information API

Source: https://pypi.org/project/distro

File(s): distro.py

License: Apache License, version 2.0. License is included with the source, unmodified.

Reason for inclusion: platform.linux_distribution is being removed in Python 3.8 and this is the commonly recommended replacement online.

# 2. Packaging.Version - an version compare API

Source: https://pypi.org/project/packaging

File(s): version.py

Reason for inclusion: distutils.LooseVersion is being removed in Python 3.11.

-----
This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). 
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or 
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

