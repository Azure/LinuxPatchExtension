#!/usr/bin/env bash
# Copyright 2020 Microsoft Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# NOTE: This script is used to detect if the VM is running on a confidential VM.
# It checks for full disk encryption and other artifacts that indicate the presence of confidential computing features.
# Please reach out to Azure Cloud Security team if you have any questions or concerns about this script.

set -euo pipefail

HOSTNAME=$(hostname)

ROOT_SRC=$(findmnt -n -o SOURCE /)
ROOT_DEV=$(readlink -f "$ROOT_SRC" || echo "$ROOT_SRC")

FDE="false"
DETAILS=""

check_device() {
   local dev="$1"

   if blkid "$dev" 2>/dev/null | grep -qi 'crypto_LUKS'; then
       FDE="true"
       DETAILS="LUKS:$dev"
       return
   fi

   local type
   type=$(lsblk -dn -o TYPE "$dev" 2>/dev/null || true)

   if [[ "$type" == "crypt" ]]; then
       FDE="true"
       DETAILS="CRYPT:$dev"
       return
   fi
}

walk_parents() {
   local dev="$1"

   while [[ -n "$dev" ]]; do
       check_device "$dev"

       if [[ "$FDE" == "true" ]]; then
           return
       fi

       local parent
       parent=$(lsblk -ndo PKNAME "$dev" 2>/dev/null | head -1 || true)

       if [[ -z "$parent" ]]; then
           break
       fi

       dev="/dev/$parent"
   done
}

walk_parents "$ROOT_DEV"

if [[ "$FDE" != "true" ]]; then
   while read -r name type; do
       if [[ "$type" == "crypt" ]]; then
           mapper="/dev/mapper/$name"

           if mount | grep -q "^$mapper on / "; then
               FDE="true"
               DETAILS="DMCRYPT_ROOT:$mapper"
               break
           fi
       fi
   done < <(dmsetup ls --target crypt 2>/dev/null || true)
fi

if [[ "$FDE" != "true" ]]; then
   if systemctl list-units 2>/dev/null | grep -qi azure; then
       if ls /var/lib/waagent/*Encryption* >/dev/null 2>&1; then
           FDE="true"
           DETAILS="AZURE_ADE_ARTIFACTS"
       fi
   fi
fi

echo "$HOSTNAME,$ROOT_DEV,FDE=$FDE,$DETAILS"

