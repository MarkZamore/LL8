StartupEvents.registry("block", event => {

  // Added Custom Deepslate Quartz Ore to Actually Additions since it had none.
  event.create("actuallyadditions:deepslate_black_quartz_ore").soundType("deepslate").hardness(5.5).tagBlock('minecraft:mineable/pickaxe').tagBlock('minecraft:needs_stone_tool').requiresTool(true).displayName('Deepslate Black Quartz Ore')

  // Added Custom Deepslate Platinum Ore to Modern Industrialization since it had none.
  event.create("modern_industrialization:deepslate_platinum_ore").soundType("deepslate").hardness(5.5).tagBlock('minecraft:mineable/pickaxe').tagBlock('minecraft:needs_stone_tool').requiresTool(true).displayName('Deepslate Platinum Ore')

  // Gunpowder Storage Block
  event.create("tnp:gunpowder_block").soundType("deepslate").hardness(4).tagBlock("minecraft:mineable/pickaxe").tagBlock("minecraft:needs_stone_tool").requiresTool(true).displayName("Block of Gunpowder")

  // Blaze Rod Storage Block
  event.create("tnp:blaze_rod_block").soundType("deepslate").hardness(4).tagBlock("minecraft:mineable/pickaxe").tagBlock("minecraft:needs_stone_tool").requiresTool(true).displayName("Block of Blaze Rods")

});