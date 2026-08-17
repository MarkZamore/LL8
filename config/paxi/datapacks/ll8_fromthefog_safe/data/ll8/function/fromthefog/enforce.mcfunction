# Herobrine may look, follow, and scare. He may not take the world apart.
#
# Every line below is the same command From The Fog's own config menu runs
# (/function fromthefog:admin/config -> the toggle), minus the part that reopens
# the menu, so this is its "off" and nothing more. It is re-applied every five
# minutes because the menu is one click away and a burned-down base is not
# something a friend can undo.

# "Give It Control": he must not rewrite his own settings.
scoreboard players set autoConfig ftf.configOptions 0

# Burns the house down once you leave it.
scoreboard players set burningBaseConfig ftf.configOptions 0
# Mines through your strip mines.
scoreboard players set ghostMineConfig ftf.configOptions 0
# Breaks your torches.
scoreboard players set poofingTorchesConfig ftf.configOptions 0
# Swaps torches for redstone torches and lanterns for soul lanterns - the lights
# stay, the light does not, and what spawns in the dark is the real damage.
scoreboard players set crimsonCurseConfig ftf.configOptions 0
# Snuffs out candles.
scoreboard players set chilledCandlesConfig ftf.configOptions 0
# Places signs of his own around the world.
scoreboard players set sinisterSignsConfig ftf.configOptions 0
# Reaches into your chests to leave "gifts".
scoreboard players set dreadfulDonationConfig ftf.configOptions 0
# Opens your doors, and whatever is outside walks in.
scoreboard players set ghostDoorConfig ftf.configOptions 0
# Relights a shrine you doused on purpose.
scoreboard players set rekindlingShrineConfig ftf.configOptions 0
# Calls lightning on a lit shrine, which sets fire to what is around it.
scoreboard players set OGshrineMechanicConfig ftf.configOptions 0
# The fake crash screen: the mod itself warns about epilepsy and weak machines.
scoreboard players set crashConfig ftf.configOptions 0

schedule function ll8:fromthefog/enforce 6000t replace
