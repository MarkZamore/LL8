# From The Fog keeps its settings in scoreboard "ftf.configOptions", and its own
# pack fills them in when the world loads. Waiting a second means this runs after
# that, whatever order the packs happen to be applied in.
schedule function ll8:fromthefog/enforce 20t replace
