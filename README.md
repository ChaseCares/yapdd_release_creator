<!-- semi-modular-release-creator by ChaseCares -->
# Semi Modular Release Creator

This is a simple python script to use for comparing two repositories and create a release if the current repositorys release doesn't match.

It is designed to work with repository secrets, it also has input validation.

# Usage

  python ./get-tags.py \
  --auth ${{ secrets.FINE_GRAINED_TOKEN }} \
  --target_owner_repo ${{ secrets.TARGET_OWNER_REPO }} \
  --local_owner_repo ${{ secrets.LOCAL_OWNER_REPO }} \
  --discord_webhook ${{ secrets.DISCORD_WEBHOOK }} \
  --tag_regex ${{ secrets.TAG_REGEX }}
