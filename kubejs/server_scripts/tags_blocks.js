ServerEvents.tags('block', event => {

  // Made GeOre budding blocks movable
  event.remove('c:relocation_not_supported', '#geore:budding_geore')

  event.remove('mekanism:cardboard_blacklist', 'geore:budding_coal', 'geore:budding_copper', 'geore:budding_diamond', 'geore:budding_emerald', 'geore:budding_gold', 'geore:budding_iron', 'geore:budding_lapis', 'geore:budding_quartz', 'geore:budding_redstone', 'geore:budding_ancient_debris', 'geore:budding_ruby', 'geore:budding_platinum', 'geore:budding_osmium', 'geore:budding_nickel', 'geore:budding_lead', 'geore:budding_aluminum', 'geore:budding_monazite', 'geore:budding_black_quartz', 'geore:budding_uraninite', 'geore:budding_zinc', 'geore:budding_topaz', 'geore:budding_sapphire', 'geore:budding_silver', 'geore:budding_tin', 'geore:budding_tungsten', 'geore:budding_uranium')

  event.remove('create:non_movable', '#geore:budding_geore')

  // Add missing tag to crops
  event.add('minecraft:crops', 'mysticalagriculture:entro_crop')

  // Tag removed due to dupes
  event.remove('c:ores/redstone', 'regions_unexplored:raw_redstone_block')
  event.remove('c:ores', 'regions_unexplored:raw_redstone_block')

  // Ores tag to custom Deepslate Black Quartz Ore
  event.add('c:ores', 'actuallyadditions:deepslate_black_quartz_ore')
  event.add('c:ores/black_quartz', 'actuallyadditions:deepslate_black_quartz_ore')

  // Fix for DimDungeons portal not working
  event.add('diagonalwalls:non_diagonal_walls', 'dimdungeons:block_portal_crown')

});