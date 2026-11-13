#!/bin/sh
# Public key only. Run manually as hengheng on the intended VPS.
set -eu
test "$(id -un)" = hengheng || { echo 'STOP: login as hengheng first'; exit 1; }
test "$(hostname)" = HENGHENG || { echo 'STOP: wrong server'; exit 1; }
umask 077
dir=/home/hengheng/.ssh
file=$dir/authorized_keys
test -d "$dir" && test -f "$file" || { echo 'STOP: existing SSH files missing'; exit 1; }
test ! -L "$dir" && test ! -L "$file" || { echo 'STOP: unexpected symlink'; exit 1; }
test "$(stat -c %U "$dir")" = hengheng
test "$(stat -c %U "$file")" = hengheng
key='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEO2OBR7sT+bF1DtSrNjj0J9hzXvuz1AZCNdgCDfs1mq dspnl-monitor'
printf '%s\n' "$key" | ssh-keygen -lf /dev/stdin
if grep -qF 'AAAAC3NzaC1lZDI1NTE5AAAAIEO2OBR7sT+bF1DtSrNjj0J9hzXvuz1AZCNdgCDfs1mq' "$file"; then
  echo 'Key already present; existing keys unchanged.'
else
  backup=$(mktemp "$dir/authorized-keys-backup.XXXXXX")
  cp -p "$file" "$backup"
  printf '\n%s\n' "$key" >> "$file"
  echo "Backup: $backup"
fi
chmod 700 "$dir"
chmod 600 "$file"
echo 'DONE: monitor SSH key added; old keys retained; no services restarted.'
