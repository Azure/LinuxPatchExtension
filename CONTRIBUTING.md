# Contributing to Azure/LinuxPatchExtension
First of all, thank you for considering contributing to the Azure LinuxPatchExtension repository!

## Basics
If you would like to become an active contributor to this project, please follow the instructions provided in [Microsoft Azure Projects Contribution Guidelines](http://azure.github.io/guidelines/).

## Table of Contents
[Before starting](#before-starting)
- [Github basics](#github-basics)
- [Code of Conduct](#code-of-conduct)

[Making Changes](#making-changes)
- [Pull Requests](#pull-requests)
- [Pull Request Guidelines](#pull-request-guidelines)
    - [PR Planning / AzGPS Engineering Requirements](#pr-planning--azgps-engineering-requirements)
    - [Cleaning up commits](#cleaning-up-commits)
    - [General guidelines](#general-guidelines)
    - [Testing guidelines](#testing-guidelines)

## Before starting

### Github basics

#### GitHub workflow

If you don't have experience with Git and Github, some of the terminology and process can be confusing. [Here's a guide to understanding Github](https://guides.github.com/introduction/flow/).

### Code of Conduct

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Making Changes

### Pull Requests

You can find all of the pull requests that have been opened in the [Pull Request](https://github.com/Azure/LinuxPatchExtension/pulls) section of the repository.

To open your own pull request, click [here](https://github.com/Azure/LinuxPatchExtension/compare). When creating a pull request, keep the following in mind:
- Make sure you are pointing to the right remote and branch that your changes were made in
- Choose the correct branch you want your pull request to be merged into
- Always give a descriptive title for the pull request and include a brief overview in description

### Pull Request Guidelines

#### PR Planning / AzGPS Engineering Requirements

The backlog for the Linux Patch Extension is tracked internally at Microsoft (by the Azure Guest Patching Service team in the Azure Core Compute Platform). There are also closed-source dependencies with the Compute Platform on this extension, and there are internal quality-control requirements set on end-to-end scenarios.

To ensure smooth engineering, if there's a change required on the extension, please proactively start a conversation with the engineering team via the Issues page. We cannot provide an SLA on unsolicited PRs if not discussed prior, so please reach out as early as possible.

#### Cleaning up Commits

If you are thinking about making a large change, **break up the change into small, logical, testable chunks, and organize your pull requests accordingly**.

Often when a pull request is created with a large number of files changed and/or a large number of lines of code added and/or removed, GitHub will have a difficult time opening up the changes on their site. 

If you find yourself creating a pull request and are unable to see all the changes on GitHub, we recommend **splitting the pull request into multiple pull requests that are able to be reviewed on GitHub**.

If splitting up the pull request is not an option, we recommend **creating individual commits for different parts of the pull request, which can be reviewed individually on GitHub**.

For more information on cleaning up the commits in a pull request, such as how to rebase, squash, and cherry-pick, click [here](https://github.com/Azure/azure-powershell/blob/main/documentation/development-docs/cleaning-up-commits.md).

#### General guidelines

The following guidelines must be followed in **EVERY** pull request that is opened.

- Title of the pull request is clear and informative.
- There are a small number of commits that each have an informative message.
- A description of the changes the pull request makes is included, and a reference to the issue being resolved, if the change address any.
- All files have the Microsoft copyright header.

#### Testing Guidelines

The following guidelines must be followed in **EVERY** pull request that is opened.

- Pull request includes test coverage for the included changes
  - All new code introduced **must not** reduce the measured code coverage of any file or of the master branch as a whole.
  - Code coverage threshold to be met: **95% on all new code.** Efforts are ongoing to meet or exceed this target on existing code.
- All existing tests must continue to pass successfully on both Python 2.7+ and Python 3.x (latest version).
- Code must have been tested on all supported distributions and versions of those distributions that have not reached end of life. The primary distribution test matrix is as follows:

Dist | Version |
-----|---------|
Ubuntu Server | 20.04-LTS, 22.04-LTS, 24.04-LTS
Red Hat Enterprise Linux | 8 (x64), 9 (x64) 
SUSE Linux Enterprise Server | 15 (x64)

The following distribution-versions are supported under **extended support policies** from the vendor and **must also be tested**:

Dist | Version | Comment |
-----|---------|---------|
Ubuntu Server | 16.04-LTS, 18.04-LTS | Until Apr 2nd, 2026 & Apr 1st, 2028 (resp.)
Red Hat Enterprise Linux | 7 (x64) | Until Jun 30th, 2024
CentOS | 7 (x64)  | Until Jun 30th, 2024
SUSE Linux Enterprise Server | 12 (x64) | Until Oct 31st, 2027

The following distributions have been **EXCLUDED** from support due to end of life and end of extended support:

Dist | Version | Comment |
-----|---------|---------|
Red Hat Enterprise Linux | 6 (x86/x64) | Ended Nov 30th, 2020
CentOS | 6 (x86/x64), 8 (x64) | Ended Nov 30th, 2020 & Dec 31st, 2021 (resp.)
SUSE Linux Enterprise Server | 11 (x86/x64) | Ended Mar 31st, 2022

**All dates listed are accurate as of March 12th, 2024. Please refer to official distribution vendor guidance for up-to-date information.**

