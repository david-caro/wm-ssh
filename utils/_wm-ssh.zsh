#compdef wm-ssh
#
# Autocomplete script for zsh.
#
# Make sure that on your ~/.zshrc file you have the lines:
#
# -----------------------------------
# fpath=$(~/.zsh-complete $fpath)  <- this one is optional
# autoload -U compinit
# compinit
# -----------------------------------
#
# then put this file under one of the directories in you $fpath (I used the 
# ~/.zsh-complete one).
# Enjoy!

hosts=($(cat ~/.cache/wm-ssh/*))

_describe 'command' hosts
