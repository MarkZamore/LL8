ServerEvents.recipes(event => {

  // Crafting Slabs back to Crafting Station
  event.shaped(Item.of('craftingstation:crafting_station'), [
    'S',
    'S',
  ], {
    S: 'craftingstation:crafting_station_slab',
  }).id('tnp:crafting_station_from_slab')

  // Silicon Press
  event.shaped(Item.of('ae2:silicon_press'), [
    'IPI',
    'PFP',
    'IPI'
  ], {
    I: 'minecraft:iron_ingot',
    P: '#c:storage_blocks/iron',
    F: '#c:storage_blocks/silicon'
  }).id('tnp:silicon_press')

  // Logic Press
  event.shaped(Item.of('ae2:logic_processor_press'), [
    'IPI',
    'PFP',
    'IPI'
  ], {
    I: 'minecraft:iron_ingot',
    P: '#c:storage_blocks/iron',
    F: 'minecraft:gold_block'
  }).id('tnp:logic_press')

  // Engineering Press
  event.shaped(Item.of('ae2:engineering_processor_press'), [
    'IPI',
    'PFP',
    'IPI'
  ], {
    I: 'minecraft:iron_ingot',
    P: '#c:storage_blocks/iron',
    F: 'minecraft:diamond_block'
  } ).id('tnp:engineering_press')

  // Calculation Press
  event.shaped(Item.of('ae2:calculation_processor_press'), [
    'IPI',
    'PFP',
    'IPI'
  ], {
    I: 'minecraft:iron_ingot',
    P: '#c:storage_blocks/iron',
    F: 'minecraft:quartz_block'
  }).id('tnp:calculation_press')

  // Earthworms
  event.shapeless(Item.of('fishofthieves:earthworms'), ['#minecraft:shovels', 'minecraft:dirt', 'minecraft:dirt', 'minecraft:dirt', 'minecraft:dirt']).damageIngredient('#minecraft:shovels').id('tnp:earthworms_from_dirt')

  // Grubs
  event.shapeless(Item.of('fishofthieves:grubs'), ['#minecraft:shovels', 'minecraft:sand', 'minecraft:sand', 'minecraft:sand', 'minecraft:sand']).damageIngredient('#minecraft:shovels').id('tnp:grubs_from_sand')

  // Leeches
  event.shapeless(Item.of('fishofthieves:leeches'), ['#minecraft:shovels', 'minecraft:mud', 'minecraft:mud', 'minecraft:mud', 'minecraft:mud']).damageIngredient('#minecraft:shovels').id('tnp:leeches_from_mud')

  // Raw Material Blocks to Metal Block
  event.smelting(Item.of('minecraft:iron_block', 1),'minecraft:raw_iron_block').cookingTime(1800).xp(6.3).id('tnp:smelt_raw_iron_block_to_metal_block')
  event.blasting(Item.of('minecraft:iron_block', 1),'minecraft:raw_iron_block').cookingTime(900).xp(6.3).id('tnp:blast_raw_iron_block_to_metal_block')
  event.smelting(Item.of('minecraft:copper_block', 1),'minecraft:raw_copper_block').cookingTime(1800).xp(6.3).id('tnp:smelt_raw_copper_block_to_metal_block')
  event.blasting(Item.of('minecraft:copper_block', 1),'minecraft:raw_copper_block').cookingTime(900).xp(6.3).id('tnp:blast_raw_copper_block_to_metal_block')
  event.smelting(Item.of('minecraft:gold_block', 1),'minecraft:raw_gold_block').cookingTime(1800).xp(9.0).id('tnp:smelt_raw_gold_block_to_metal_block')
  event.blasting(Item.of('minecraft:gold_block', 1),'minecraft:raw_gold_block').cookingTime(900).xp(9.0).id('tnp:blast_raw_gold_block_to_metal_block')
  event.smelting(Item.of('occultism:silver_block', 1),'occultism:raw_silver_block').cookingTime(1800).xp(9.0).id('tnp:smelt_raw_silver_block_to_metal_block')
  event.blasting(Item.of('occultism:silver_block', 1),'occultism:raw_silver_block').cookingTime(900).xp(9.0).id('tnp:blast_raw_silver_block_to_metal_block')
  event.smelting(Item.of('occultism:iesnium_block', 1),'occultism:raw_iesnium_block').cookingTime(1800).xp(6.3).id('tnp:smelt_raw_iesnium_block_to_metal_block')
  event.blasting(Item.of('occultism:iesnium_block', 1),'occultism:raw_iesnium_block').cookingTime(900).xp(6.3).id('tnp:blast_raw_iesnium_block_to_metal_block')
  event.smelting(Item.of('undergarden:cloggrum_block', 1),'undergarden:raw_cloggrum_block').cookingTime(1800).xp(6.3).id('tnp:smelt_raw_cloggrum_block_to_metal_block')
  event.blasting(Item.of('undergarden:cloggrum_block', 1),'undergarden:raw_cloggrum_block').cookingTime(900).xp(6.3).id('tnp:blast_raw_cloggrum_block_to_metal_block')
  event.smelting(Item.of('undergarden:froststeel_block', 1),'undergarden:raw_froststeel_block').cookingTime(1800).xp(6.3).id('tnp:smelt_raw_froststeel_block_to_metal_block')
  event.blasting(Item.of('undergarden:froststeel_block', 1),'undergarden:raw_froststeel_block').cookingTime(900).xp(6.3).id('tnp:blast_raw_froststeel_block_to_metal_block')
  event.smelting(Item.of('eternal_starlight:aethersent_block', 1),'eternal_starlight:raw_aethersent_block').cookingTime(1800).xp(9.0).id('tnp:smelt_raw_aethersent_block_to_metal_block')
  event.blasting(Item.of('eternal_starlight:aethersent_block', 1),'eternal_starlight:raw_aethersent_block').cookingTime(900).xp(9.0).id('tnp:blast_raw_aethersent_block_to_metal_block')
  event.smelting(Item.of('silentgear:crimson_iron_block', 1),'silentgear:raw_crimson_iron_block').cookingTime(1800).xp(9.0).id('tnp:smelt_raw_crimson_iron_block_to_metal_block')
  event.blasting(Item.of('silentgear:crimson_iron_block', 1),'silentgear:raw_crimson_iron_block').cookingTime(900).xp(9.0).id('tnp:blast_raw_crimson_iron_block_to_metal_block')
  event.smelting(Item.of('silentgear:azure_silver_block', 1),'silentgear:raw_azure_silver_block').cookingTime(1800).xp(13.5).id('tnp:smelt_raw_azure_silver_block_to_metal_block')
  event.blasting(Item.of('silentgear:azure_silver_block', 1),'silentgear:raw_azure_silver_block').cookingTime(900).xp(13.5).id('tnp:blast_raw_azure_silver_block_to_metal_block')
  event.smelting(Item.of('mekanism:block_osmium', 1),'mekanism:block_raw_osmium').cookingTime(1800).xp(5.4).id('tnp:smelt_raw_block_osmium_to_metal_block')
  event.blasting(Item.of('mekanism:block_osmium', 1),'mekanism:block_raw_osmium').cookingTime(900).xp(5.4).id('tnp:blast_raw_block_osmium_to_metal_block')
  event.smelting(Item.of('mekanism:block_tin', 1),'mekanism:block_raw_tin').cookingTime(1800).xp(6.3).id('tnp:smelt_raw_block_tin_to_metal_block')
  event.blasting(Item.of('mekanism:block_tin', 1),'mekanism:block_raw_tin').cookingTime(900).xp(6.3).id('tnp:blast_raw_block_tin_to_metal_block')
  event.smelting(Item.of('mekanism:block_lead', 1),'mekanism:block_raw_lead').cookingTime(1800).xp(6.3).id('tnp:smelt_raw_block_lead_to_metal_block')
  event.blasting(Item.of('mekanism:block_lead', 1),'mekanism:block_raw_lead').cookingTime(900).xp(6.3).id('tnp:blast_raw_block_lead_to_metal_block')
  event.smelting(Item.of('mekanism:block_uranium', 1),'mekanism:block_raw_uranium').cookingTime(1800).xp(9.0).id('tnp:smelt_raw_block_uranium_to_metal_block')
  event.blasting(Item.of('mekanism:block_uranium', 1),'mekanism:block_raw_uranium').cookingTime(900).xp(9.0).id('tnp:blast_raw_block_uranium_to_metal_block')
  event.smelting(Item.of('modern_industrialization:aluminum_block', 1),'immersiveengineering:raw_block_aluminum').cookingTime(1800).xp(2.7).id('tnp:smelt_raw_block_aluminum_to_metal_block')
  event.blasting(Item.of('modern_industrialization:aluminum_block', 1),'immersiveengineering:raw_block_aluminum').cookingTime(900).xp(2.7).id('tnp:blast_raw_block_aluminum_to_metal_block')
  event.smelting(Item.of('bigreactors:yellorium_block', 1),'bigreactors:raw_yellorium_block').cookingTime(1800).xp(9.0).id('tnp:smelt_raw_yellorium_block_to_metal_block')
  event.blasting(Item.of('bigreactors:yellorium_block', 1),'bigreactors:raw_yellorium_block').cookingTime(900).xp(9.0).id('tnp:blast_raw_yellorium_block_to_metal_block')
  event.smelting(Item.of('create:zinc_block', 1),'create:raw_zinc_block').cookingTime(1800).xp(6.3).id('tnp:smelt_raw_zinc_block_to_metal_block')
  event.blasting(Item.of('create:zinc_block', 1),'create:raw_zinc_block').cookingTime(900).xp(6.3).id('tnp:blast_raw_zinc_block_to_metal_block')
  event.smelting(Item.of('mekanism:block_steel', 1),'stellaris:raw_steel_block').cookingTime(1800).xp(6.3).id('tnp:smelt_raw_steel_block_to_metal_block')
  event.blasting(Item.of('mekanism:block_steel', 1),'stellaris:raw_steel_block').cookingTime(900).xp(6.3).id('tnp:blast_raw_steel_block_to_metal_block')
  event.smelting(Item.of('modern_industrialization:antimony_block', 1),'modern_industrialization:raw_antimony_block').cookingTime(1800).xp(6.3).id('tnp:smelt_raw_antimony_block_to_metal_block')
  event.blasting(Item.of('modern_industrialization:antimony_block', 1),'modern_industrialization:raw_antimony_block').cookingTime(900).xp(6.3).id('tnp:blast_raw_antimony_block_to_metal_block')
  event.smelting(Item.of('modern_industrialization:iridium_block', 1),'modern_industrialization:raw_iridium_block').cookingTime(1800).xp(6.3).id('tnp:smelt_raw_iridium_block_to_metal_block')
  event.blasting(Item.of('modern_industrialization:iridium_block', 1),'modern_industrialization:raw_iridium_block').cookingTime(900).xp(6.3).id('tnp:blast_raw_iridium_block_to_metal_block')
  event.smelting(Item.of('modern_industrialization:nickel_block', 1),'modern_industrialization:raw_nickel_block').cookingTime(1800).xp(9.0).id('tnp:smelt_raw_nickel_block_to_metal_block')
  event.blasting(Item.of('modern_industrialization:nickel_block', 1),'modern_industrialization:raw_nickel_block').cookingTime(900).xp(9.0).id('tnp:blast_raw_nickel_block_to_metal_block')
  event.smelting(Item.of('modern_industrialization:platinum_block', 1),'modern_industrialization:raw_platinum_block').cookingTime(1800).xp(9.0).id('tnp:smelt_raw_platinum_block_to_metal_block')
  event.blasting(Item.of('modern_industrialization:platinum_block', 1),'modern_industrialization:raw_platinum_block').cookingTime(900).xp(9.0).id('tnp:blast_raw_platinum_block_to_metal_block')
  event.blasting(Item.of('instrumentus:soulcopper_block', 1),'instrumentus:raw_soulcopper_block').cookingTime(900).xp(6.3).id('tnp:blast_raw_soulcopper_block_to_metal_block')

  // Revert GeOre Blocks back to a few shards
  event.shapeless(Item.of('geore:coal_shard', 2), ['#c:tools/mining_tool', 'geore:coal_block']).damageIngredient('#c:tools/mining_tool').id('tnp:coal_shard_from_block')
  event.shapeless(Item.of('geore:copper_shard', 2), ['#c:tools/mining_tool', 'geore:copper_block']).damageIngredient('#c:tools/mining_tool').id('tnp:copper_shard_from_block')
  event.shapeless(Item.of('geore:diamond_shard', 2), ['#c:tools/mining_tool', 'geore:diamond_block']).damageIngredient('#c:tools/mining_tool').id('tnp:diamond_shard_from_block')
  event.shapeless(Item.of('geore:emerald_shard', 2), ['#c:tools/mining_tool', 'geore:emerald_block']).damageIngredient('#c:tools/mining_tool').id('tnp:emerald_shard_from_block')
  event.shapeless(Item.of('geore:gold_shard', 2), ['#c:tools/mining_tool', 'geore:gold_block']).damageIngredient('#c:tools/mining_tool').id('tnp:gold_shard_from_block')
  event.shapeless(Item.of('geore:iron_shard', 2), ['#c:tools/mining_tool', 'geore:iron_block']).damageIngredient('#c:tools/mining_tool').id('tnp:iron_shard_from_block')
  event.shapeless(Item.of('geore:lapis_shard', 2), ['#c:tools/mining_tool', 'geore:lapis_block']).damageIngredient('#c:tools/mining_tool').id('tnp:lapis_shard_from_block')
  event.shapeless(Item.of('geore:quartz_shard', 2), ['#c:tools/mining_tool', 'geore:quartz_block']).damageIngredient('#c:tools/mining_tool').id('tnp:quartz_shard_from_block')
  event.shapeless(Item.of('geore:redstone_shard', 2), ['#c:tools/mining_tool', 'geore:redstone_block']).damageIngredient('#c:tools/mining_tool').id('tnp:redstone_shard_from_block')
  event.shapeless(Item.of('geore:ancient_debris_shard', 2), ['#c:tools/mining_tool', 'geore:ancient_debris_block']).damageIngredient('#c:tools/mining_tool').id('tnp:ancient_debris_shard_from_block')
  event.shapeless(Item.of('geore:ruby_shard', 2), ['#c:tools/mining_tool', 'geore:ruby_block']).damageIngredient('#c:tools/mining_tool').id('tnp:ruby_shard_from_block')
  event.shapeless(Item.of('geore:sapphire_shard', 2), ['#c:tools/mining_tool', 'geore:sapphire_block']).damageIngredient('#c:tools/mining_tool').id('tnp:sapphire_shard_from_block')
  event.shapeless(Item.of('geore:topaz_shard', 2), ['#c:tools/mining_tool', 'geore:topaz_block']).damageIngredient('#c:tools/mining_tool').id('tnp:topaz_shard_from_block')
  event.shapeless(Item.of('geore:zinc_shard', 2), ['#c:tools/mining_tool', 'geore:zinc_block']).damageIngredient('#c:tools/mining_tool').id('tnp:zinc_shard_from_block')
  event.shapeless(Item.of('geore:uraninite_shard', 2), ['#c:tools/mining_tool', 'geore:uraninite_block']).damageIngredient('#c:tools/mining_tool').id('tnp:uraninite_shard_from_block')
  event.shapeless(Item.of('geore:black_quartz_shard', 2), ['#c:tools/mining_tool', 'geore:black_quartz_block']).damageIngredient('#c:tools/mining_tool').id('tnp:black_quartz_shard_from_block')
  event.shapeless(Item.of('geore:monazite_shard', 2), ['#c:tools/mining_tool', 'geore:monazite_block']).damageIngredient('#c:tools/mining_tool').id('tnp:monazite_shard_from_block')
  event.shapeless(Item.of('geore:aluminum_shard', 2), ['#c:tools/mining_tool', 'geore:aluminum_block']).damageIngredient('#c:tools/mining_tool').id('tnp:aluminum_shard_from_block')
  event.shapeless(Item.of('geore:lead_shard', 2), ['#c:tools/mining_tool', 'geore:lead_block']).damageIngredient('#c:tools/mining_tool').id('tnp:lead_shard_from_block')
  event.shapeless(Item.of('geore:nickel_shard', 2), ['#c:tools/mining_tool', 'geore:nickel_block']).damageIngredient('#c:tools/mining_tool').id('tnp:nickel_shard_from_block')
  event.shapeless(Item.of('geore:osmium_shard', 2), ['#c:tools/mining_tool', 'geore:osmium_block']).damageIngredient('#c:tools/mining_tool').id('tnp:osmium_shard_from_block')
  event.shapeless(Item.of('geore:platinum_shard', 2), ['#c:tools/mining_tool', 'geore:platinum_block']).damageIngredient('#c:tools/mining_tool').id('tnp:platinum_shard_from_block')
  event.shapeless(Item.of('geore:silver_shard', 2), ['#c:tools/mining_tool', 'geore:silver_block']).damageIngredient('#c:tools/mining_tool').id('tnp:silver_shard_from_block')
  event.shapeless(Item.of('geore:tin_shard', 2), ['#c:tools/mining_tool', 'geore:tin_block']).damageIngredient('#c:tools/mining_tool').id('tnp:tin_shard_from_block')
  event.shapeless(Item.of('geore:tungsten_shard', 2), ['#c:tools/mining_tool', 'geore:tungsten_block']).damageIngredient('#c:tools/mining_tool').id('tnp:tungsten_shard_from_block')
  event.shapeless(Item.of('geore:uranium_shard', 2), ['#c:tools/mining_tool', 'geore:uranium_block']).damageIngredient('#c:tools/mining_tool').id('tnp:uranium_shard_from_block')

  // GeOre (Actually Additions) -  Break down Blocks to Shards 1:1
  event.recipes.actuallyadditions.crushing("4x geore:coal_shard", "geore:coal_block").id('aa_geore_coal_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:copper_shard", "geore:copper_block").id('aa_geore_copper_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:diamond_shard", "geore:diamond_block").id('aa_geore_diamond_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:emerald_shard", "geore:emerald_block").id('aa_geore_emerald_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:gold_shard", "geore:gold_block").id('aa_geore_gold_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:iron_shard", "geore:iron_block").id('aa_geore_iron_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:lapis_shard", "geore:lapis_block").id('aa_geore_lapis_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:quartz_shard", "geore:quartz_block").id('aa_geore_quartz_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:redstone_shard", "geore:redstone_block").id('aa_geore_redstone_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:ancient_debris_shard", "geore:ancient_debris_block").id('aa_geore_ancient_debris_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:ruby_shard", "geore:ruby_block").id('aa_geore_ruby_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:sapphire_shard", "geore:sapphire_block").id('aa_geore_sapphire_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:topaz_shard", "geore:topaz_block").id('aa_geore_topaz_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:zinc_shard", "geore:zinc_block").id('aa_geore_zinc_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:uraninite_shard", "geore:uraninite_block").id('aa_geore_uraninite_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:black_quartz_shard", "geore:black_quartz_block").id('aa_geore_black_quartz_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:monazite_shard", "geore:monazite_block").id('aa_geore_monazite_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:aluminum_shard", "geore:aluminum_block").id('aa_geore_aluminum_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:lead_shard", "geore:lead_block").id('aa_geore_lead_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:nickel_shard", "geore:nickel_block").id('aa_geore_nickel_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:osmium_shard", "geore:osmium_block").id('aa_geore_osmium_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:platinum_shard", "geore:platinum_block").id('aa_geore_platinum_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:silver_shard", "geore:silver_block").id('aa_geore_silver_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:tin_shard", "geore:tin_block").id('aa_geore_tin_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:tungsten_shard", "geore:tungsten_block").id('aa_geore_tungsten_block_to_shards')
  event.recipes.actuallyadditions.crushing("4x geore:uranium_shard", "geore:uranium_block").id('aa_geore_uranium_block_to_shards')

  // GeOre (Ender IO) -  Break down Blocks to Shards 1:1
  event.recipes.enderio.sag_milling(["4x geore:coal_shard"], "geore:coal_block").bonus(SagMillBonus.NONE).id('eio_geore_coal_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:copper_shard"], "geore:copper_block").bonus(SagMillBonus.NONE).id('eio_geore_copper_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:diamond_shard"], "geore:diamond_block").bonus(SagMillBonus.NONE).id('eio_geore_diamond_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:emerald_shard"], "geore:emerald_block").bonus(SagMillBonus.NONE).id('eio_geore_emerald_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:gold_shard"], "geore:gold_block").bonus(SagMillBonus.NONE).id('eio_geore_gold_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:iron_shard"], "geore:iron_block").bonus(SagMillBonus.NONE).id('eio_geore_iron_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:lapis_shard"], "geore:lapis_block").bonus(SagMillBonus.NONE).id('eio_geore_lapis_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:quartz_shard"], "geore:quartz_block").bonus(SagMillBonus.NONE).id('eio_geore_quartz_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:redstone_shard"], "geore:redstone_block").bonus(SagMillBonus.NONE).id('eio_geore_redstone_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:ancient_debris_shard"], "geore:ancient_debris_block").bonus(SagMillBonus.NONE).id('eio_geore_ancient_debris_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:ruby_shard"], "geore:ruby_block").bonus(SagMillBonus.NONE).id('eio_geore_ruby_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:sapphire_shard"], "geore:sapphire_block").bonus(SagMillBonus.NONE).id('eio_geore_sapphire_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:topaz_shard"], "geore:topaz_block").bonus(SagMillBonus.NONE).id('eio_geore_topaz_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:zinc_shard"], "geore:zinc_block").bonus(SagMillBonus.NONE).id('eio_geore_zinc_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:uraninite_shard"], "geore:uraninite_block").bonus(SagMillBonus.NONE).id('eio_geore_uraninite_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:black_quartz_shard"], "geore:black_quartz_block").bonus(SagMillBonus.NONE).id('eio_geore_black_quartz_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:monazite_shard"], "geore:monazite_block").bonus(SagMillBonus.NONE).id('eio_geore_monazite_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:aluminum_shard"], "geore:aluminum_block").bonus(SagMillBonus.NONE).id('eio_geore_aluminum_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:lead_shard"], "geore:lead_block").bonus(SagMillBonus.NONE).id('eio_geore_lead_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:nickel_shard"], "geore:nickel_block").bonus(SagMillBonus.NONE).id('eio_geore_nickel_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:osmium_shard"], "geore:osmium_block").bonus(SagMillBonus.NONE).id('eio_geore_osmium_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:platinum_shard"], "geore:platinum_block").bonus(SagMillBonus.NONE).id('eio_geore_platinum_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:silver_shard"], "geore:silver_block").bonus(SagMillBonus.NONE).id('eio_geore_silver_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:tin_shard"], "geore:tin_block").bonus(SagMillBonus.NONE).id('eio_geore_tin_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:tungsten_shard"], "geore:tungsten_block").bonus(SagMillBonus.NONE).id('eio_geore_tungsten_block_to_shards')
  event.recipes.enderio.sag_milling(["4x geore:uranium_shard"], "geore:uranium_block").bonus(SagMillBonus.NONE).id('eio_geore_uranium_block_to_shards')

  // GeOre (Mekanism) -  Break down Blocks to Shards 1:1
  event.recipes.mekanismCrushing('4x geore:coal_shard', 'geore:coal_block').id('mek_geore_coal_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:copper_shard', 'geore:copper_block').id('mek_geore_copper_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:diamond_shard', 'geore:diamond_block').id('mek_geore_diamond_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:emerald_shard', 'geore:emerald_block').id('mek_geore_emerald_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:gold_shard', 'geore:gold_block').id('mek_geore_gold_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:iron_shard', 'geore:iron_block').id('mek_geore_iron_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:lapis_shard', 'geore:lapis_block').id('mek_geore_lapis_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:quartz_shard', 'geore:quartz_block').id('mek_geore_quartz_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:redstone_shard', 'geore:redstone_block').id('mek_geore_redstone_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:ancient_debris_shard', 'geore:ancient_debris_block').id('mek_geore_ancient_debris_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:ruby_shard', 'geore:ruby_block').id('mek_geore_ruby_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:sapphire_shard', 'geore:sapphire_block').id('mek_geore_sapphire_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:topaz_shard', 'geore:topaz_block').id('mek_geore_topaz_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:zinc_shard', 'geore:zinc_block').id('mek_geore_zinc_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:uraninite_shard', 'geore:uraninite_block').id('mek_geore_uraninite_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:black_quartz_shard', 'geore:black_quartz_block').id('mek_geore_black_quartz_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:monazite_shard', 'geore:monazite_block').id('mek_geore_monazite_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:aluminum_shard', 'geore:aluminum_block').id('mek_geore_aluminum_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:lead_shard', 'geore:lead_block').id('mek_geore_lead_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:nickel_shard', 'geore:nickel_block').id('mek_geore_nickel_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:osmium_shard', 'geore:osmium_block').id('mek_geore_osmium_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:platinum_shard', 'geore:platinum_block').id('mek_geore_platinum_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:silver_shard', 'geore:silver_block').id('mek_geore_silver_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:tin_shard', 'geore:tin_block').id('mek_geore_tin_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:tungsten_shard', 'geore:tungsten_block').id('mek_geore_tungsten_block_to_shards')
  event.recipes.mekanismCrushing('4x geore:uranium_shard', 'geore:uranium_block').id('mek_geore_uranium_block_to_shards')

  // GeOre (Oritech) -  Break down Blocks to Shards 1:1
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:coal_shard").itemInputs("geore:coal_block").id('ori_geore_coal_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:copper_shard").itemInputs("geore:copper_block").id('ori_geore_copper_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:diamond_shard").itemInputs("geore:diamond_block").id('ori_geore_diamond_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:emerald_shard").itemInputs("geore:emerald_block").id('ori_geore_emerald_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:gold_shard").itemInputs("geore:gold_block").id('ori_geore_gold_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:iron_shard").itemInputs("geore:iron_block").id('ori_geore_iron_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:lapis_shard").itemInputs("geore:lapis_block").id('ori_geore_lapis_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:quartz_shard").itemInputs("geore:quartz_block").id('ori_geore_quartz_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:redstone_shard").itemInputs("geore:redstone_block").id('ori_geore_redstone_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:ancient_debris_shard").itemInputs("geore:ancient_debris_block").id('ori_geore_ancient_debris_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:ruby_shard").itemInputs("geore:ruby_block").id('ori_geore_ruby_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:sapphire_shard").itemInputs("geore:sapphire_block").id('ori_geore_sapphire_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:topaz_shard").itemInputs("geore:topaz_block").id('ori_geore_topaz_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:zinc_shard").itemInputs("geore:zinc_block").id('ori_geore_zinc_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:uraninite_shard").itemInputs("geore:uraninite_block").id('ori_geore_uraninite_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:black_quartz_shard").itemInputs("geore:black_quartz_block").id('ori_geore_black_quartz_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:monazite_shard").itemInputs("geore:monazite_block").id('ori_geore_monazite_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:aluminum_shard").itemInputs("geore:aluminum_block").id('ori_geore_aluminum_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:lead_shard").itemInputs("geore:lead_block").id('ori_geore_lead_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:nickel_shard").itemInputs("geore:nickel_block").id('ori_geore_nickel_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:osmium_shard").itemInputs("geore:osmium_block").id('ori_geore_osmium_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:platinum_shard").itemInputs("geore:platinum_block").id('ori_geore_platinum_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:silver_shard").itemInputs("geore:silver_block").id('ori_geore_silver_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:tin_shard").itemInputs("geore:tin_block").id('ori_geore_tin_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:tungsten_shard").itemInputs("geore:tungsten_block").id('ori_geore_tungsten_block_to_shards')
  event.recipes.oritech.pulverizer().itemOutputs("4x geore:uranium_shard").itemInputs("geore:uranium_block").id('ori_geore_uranium_block_to_shards')

  // Croptopia - Knife Fix
  event.remove({id: 'croptopia:knife'})
  event.shaped(Item.of('croptopia:knife'), [
    ' I ',
    ' I ',
    'R  '
  ], {
    I: 'minecraft:iron_ingot',
    R: '#c:rods/wooden'
  }).id('tnp:ct_knife_fix')

  // Croptopia Flour - Fix
  event.remove({id: 'croptopia:flour'})
  event.shaped(Item.of('croptopia:flour'), [
    'F ',
    'F '
  ], {
    F: '#c:flour'
  }).id('tnp:ct_flour_fix')

  // Tesseract - Edit
  event.remove({id: 'tesseract:tesseract'})
  event.shaped(Item.of('tesseract:tesseract'), [
    'ICI',
    'ETE',
    'ICI'
  ], {
    I: 'minecraft:crying_obsidian',
    C: 'extendedae:concurrent_processor_print',
    E: '#c:ingots/eclipsealloy',
    T: 'irons_spellbooks:scroll[irons_spellbooks:spell_container={data:[{id:"irons_spellbooks:teleport",index:0,level:5,locked:1b}],maxSpells:1,mustEquip:0b,spellWheel:0b}]'
  }).id('tnp:tesseract_edit')

  // Comforts - White Sleeping Bag
  event.remove({id: 'comforts:sleeping_bag_white'})
  event.shaped(Item.of('comforts:sleeping_bag_white'), [
    'L L',
    'WWW',
    'L L'
  ], {
    L: '#c:leathers',
    W: '#minecraft:wool'
  }).id('tnp:comforts_sleeping_bag')

  // Regions Unexplored Dirt to Vanilla Dirt
  event.shapeless(Item.of('minecraft:dirt'), ['regions_unexplored:ashen_dirt']).id('tnp:ashen_dirt_to_dirt')
  event.shapeless(Item.of('minecraft:dirt'), ['regions_unexplored:peat_dirt']).id('tnp:peat_dirt_to_dirt')
  event.shapeless(Item.of('minecraft:dirt'), ['regions_unexplored:silt_dirt']).id('tnp:silt_dirt_to_dirt')

  // Regions Unexplored Coarse Dirt to Vanilla Coarse Dirt
  event.shapeless(Item.of('minecraft:coarse_dirt'), ['regions_unexplored:silt_coarse_dirt']).id('tnp:silt_coarse_dirt_to_coarse_dirt')
  event.shapeless(Item.of('minecraft:coarse_dirt'), ['regions_unexplored:peat_coarse_dirt']).id('tnp:peat_coarse_dirt_to_coarse_dirt')

  // Biomes Weve Gone Lush Dirt to Vanilla Dirt
  event.shapeless(Item.of('minecraft:dirt'), ['biomeswevegone:lush_dirt']).id('tnp:lush_dirt_to_dirt')

  // Temporal Pouch - Edit
  event.remove({id: 'gag:time_sand_pouch'})
  event.shaped(Item.of('gag:time_sand_pouch'), [
    'SGS',
    'NBN',
    'RCR'
  ], {
    N: 'minecraft:netherite_ingot',
    G: 'minecraft:nautilus_shell',
    S: 'evilcraft:golden_string',
    C: 'minecraft:clock',
    B: 'minecraft:bundle',
    R: 'minecraft:raw_gold_block'
  }).id('tnp:temporal_pouch')

  // Raw Redstone Block back to 2x Redstone Dust
  event.shapeless(Item.of('minecraft:redstone', 2), ['regions_unexplored:raw_redstone_block']).id('tnp:raw_redstone_block_back_to_redstone_dust')

  // Click Machine - Edit
  event.remove({id: 'clickmachine:click_machine'})
  event.shaped(Item.of('clickmachine:click_machine'), [
    'DDD',
    'DLD',
    'DRD'
  ], {
    D: 'minecraft:diorite',
    L: 'minecraft:lapis_block',
    R: '#c:storage_blocks/redstone'
  }).id('tnp:click_machine')

  // Magicbane - New recipe
  event.remove({id: 'reliquary:magicbane'})
  event.shaped(Item.of('reliquary:magicbane'), [
    'EAT',
    'BSU',
    'WCM'
  ], {
    E: 'ars_nouveau:earth_essence',
    A: 'minecraft:enchanted_golden_apple',
    T: 'ars_nouveau:conjuration_essence',
    B: 'minecraft:experience_bottle',
    S: 'ars_nouveau:enchanters_sword',
    U: 'tombstone:essence_of_undeath',
    W: 'ars_nouveau:water_essence',
    C: 'silentgems:chaos_essence',
    M: 'ars_nouveau:manipulation_essence'
  }).id('tnp:magicbane')

  // Filled Morph-O-Tool
  event.remove({id: 'morphtool:tool'})
  event.shaped(Item.of('morphtool:tool[morphtool:tool_content=[{count:1,id:"actuallyadditions:laser_wrench"},{count:1,id:"integrateddynamics:wrench"},{count:1,id:"ae2:certus_quartz_wrench"},{count:1,id:"ae2:nether_quartz_wrench"},{count:1,id:"cable_facades:facade_wrench"},{count:1,id:"enderio:yeta_wrench"},{count:1,id:"bigreactors:wrench"},{count:1,id:"framedblocks:framed_wrench"},{count:1,id:"hammerlib:wrench"},{count:1,id:"justdirethings:ferricore_wrench"},{count:1,id:"laserio:laser_wrench"},{count:1,id:"moderndynamics:wrench"},{count:1,id:"modern_industrialization:wrench"},{count:1,id:"refurbished_furniture:wrench"},{count:1,id:"pipez:wrench"},{count:1,id:"powah:wrench"},{count:1,id:"prettypipes:wrench"},{count:1,id:"rftoolsbase:smartwrench"},{count:1,id:"rftoolsbase:smartwrench_select"},{count:1,id:"advanced_ae:throughput_monitor_configurator"},{count:1,id:"immersiveengineering:hammer"},{count:1,id:"oritech:wrench"},{count:1,id:"energizedpower:wrench"}]]'), [
    ' GB',
    ' IR',
    'I  '
  ], {
    I: 'minecraft:iron_ingot',
    R: '#c:dyes/red',
    G: '#c:dyes/green',
    B: '#c:dyes/blue'
  }).id('tnp:filled_morphtool')

  // Filled Eccentric Tome
  event.remove({id: 'eccentrictome:tome'})
  event.shapeless(Item.of('eccentrictome:tome[eccentrictome:tome_data={books:{actuallyadditions:[{count:1,id:"actuallyadditions:booklet"}],advancedperipherals:[{components:{"patchouli:book":"advancedperipherals:manual"},count:1,id:"patchouli:guide_book"}],ae2:[{count:1,id:"ae2:guide"}],aether:[{count:1,id:"aether:book_of_lore"}],apotheosis:[{components:{"patchouli:book":"apotheosis:apoth_chronicle"},count:1,id:"patchouli:guide_book"}],bigreactors:[{components:{"patchouli:book":"bigreactors:erguide"},count:1,id:"patchouli:guide_book"}],buildinggadgets2:[{components:{"patchouli:book":"buildinggadgets2:buildinggadgets2book"},count:1,id:"patchouli:guide_book"}],chococraft:[{count:1,id:"chococraft:chocopedia"}],dimdungeons:[{components:{"patchouli:book":"dimdungeons:guide_book"},count:1,id:"patchouli:guide_book"}],energizedpower:[{count:1,id:"energizedpower:energized_power_book"}],eternal_starlight:[{count:1,id:"eternal_starlight:book"}],extendedcrafting:[{components:{"patchouli:book":"extendedcrafting:guide"},count:1,id:"patchouli:guide_book"}],ftbquests:[{count:1,id:"ftbquests:book"}],hostile_neural_industrialization:[{count:1,id:"hostile_neural_industrialization:guidebook"}],immersiveengineering:[{count:1,id:"immersiveengineering:manual"}],industrialforegoing:[{components:{"patchouli:book":"industrialforegoing:industrial_foregoing"},count:1,id:"patchouli:guide_book"}],integrateddynamics:[{count:1,id:"integrateddynamics:on_the_dynamics_of_integration"}],irons_spellbooks:[{components:{"patchouli:book":"irons_spellbooks:iss_guide_book"},count:1,id:"patchouli:guide_book"}],justdirethings:[{components:{"patchouli:book":"justdirethings:justdirethingsbook"},count:1,id:"patchouli:guide_book"}],laserio:[{components:{"patchouli:book":"laserio:laseriobook"},count:1,id:"patchouli:guide_book"}],linkingbooks:[{count:1,id:"linkingbooks:guidebook"}],livingthings:[{count:1,id:"livingthings:lexicon"}],mahoutsukai:[{count:1,id:"mahoutsukai:guidebook"}],malum:[{count:1,id:"malum:encyclopedia_arcana"}],modern_industrialization:[{count:1,id:"modern_industrialization:guidebook"}],modonomicon:[{components:{"modonomicon:book_id":"theurgy:the_hermetica"},count:1,id:"modonomicon:modonomicon"}],modularrouters:[{components:{"patchouli:book":"modularrouters:book"},count:1,id:"patchouli:guide_book"}],moresnifferflowers:[{count:1,id:"moresnifferflowers:beroot_cook_book"}],mysticalagriculture:[{components:{"patchouli:book":"mysticalagriculture:guide"},count:1,id:"patchouli:guide_book"}],naturesaura:[{components:{"patchouli:book":"naturesaura:book"},count:1,id:"patchouli:guide_book"}],occultism:[{components:{"modonomicon:book_id":"occultism:dictionary_of_spirits"},count:1,id:"occultism:dictionary_of_spirits"}],packagedauto:[{components:{"patchouli:book":"packagedauto:guide"},count:1,id:"patchouli:guide_book"}],pastel:[{count:1,id:"pastel:guidebook"}],pneumaticcraft:[{components:{"patchouli:book":"pneumaticcraft:book"},count:1,id:"patchouli:guide_book"}],powah:[{count:1,id:"powah:book"}],productivebees:[{components:{"patchouli:book":"productivebees:guide"},count:1,id:"patchouli:guide_book"}],productivemetalworks:[{components:{"patchouli:book":"productivemetalworks:guide"},count:1,id:"patchouli:guide_book"}],productivetrees:[{components:{"patchouli:book":"productivetrees:guide"},count:1,id:"patchouli:guide_book"}],rftoolsbase:[{count:1,id:"rftoolsbase:manual"}],securitycraft:[{count:1,id:"securitycraft:sc_manual"}],silentgear:[{count:1,id:"silentgear:guide_book"}],solcarrot:[{count:1,id:"solcarrot:food_book"}],starcatcher:[{count:1,id:"starcatcher:starcatcher_guide"}],sushigocrafting:[{components:{"patchouli:book":"sushigocrafting:sushigocrafting"},count:1,id:"patchouli:guide_book"}],twilightdelight:[{components:{"patchouli:book":"twilightdelight:twilight_guide"},count:1,id:"patchouli:guide_book"}],woot_revived:[{count:1,id:"woot_revived:guide"}]},tome_id:"7e45f515-195b-445c-96d1-a824af17d402"}]'), ['minecraft:book', '#c:bookshelves']).id('tnp:filled_eccentric_tome')

  // Ender Pearl to any Ender Pearl
  event.replaceInput({}, 'minecraft:ender_pearl', '#c:ender_pearls')

  // Copper Button - Fix
  event.remove({output: 'friendsandfoes:copper_button'})
  event.shapeless(Item.of('friendsandfoes:copper_button'), ['minecraft:copper_ingot', '#minecraft:buttons']).id('tnp:copper_button_fix')

  // Sliced Potato to Baked Sliced Potato
  event.smelting(Item.of('rusticdelight:baked_potato_slices', 1),'extradelight:sliced_potato').xp(0.35).id('tnp:baked_sliced_potato_smelt')
  event.smoking(Item.of('rusticdelight:baked_potato_slices', 1), 'extradelight:sliced_potato').xp(0.35).id('tnp:baked_sliced_potato_smoked')
  event.campfireCooking('rusticdelight:baked_potato_slices', 'extradelight:sliced_potato').id('tnp:baked_sliced_potato_campfire')

  // Ink Sac Alternative Recipe
  event.shaped(Item.of('minecraft:ink_sac', 3), [
    'SPG',
    'WDW',
    'GPS'
  ], {
    S: '#c:salts',
    P: 'powah:dielectric_paste',
    G: 'minecraft:seagrass',
    W: 'extradelight:seaweed_paste',
    D: '#c:dyes/white'
  }).id('tnp:ink_sac_alt')

  // Gunpowder Block
  event.shaped('tnp:gunpowder_block', [
    'GGG',
    'GGG',
    'GGG'
  ], {
    G: 'minecraft:gunpowder',
  }).id('tnp:gunpowder_block')

  // Gunpowder Block Revert
  event.shapeless('9x minecraft:gunpowder', ['tnp:gunpowder_block']).id('tnp:gunpowder_block_revert')

  // Blaze Rod Block
  event.shaped('tnp:blaze_rod_block', [
    'BBB',
    'BBB',
    'BBB'
  ], {
    B: 'minecraft:blaze_rod',
  }).id('tnp:blaze_rod_block')

  // Blaze Rod Block Revert
  event.shapeless('9x minecraft:blaze_rod', ['tnp:blaze_rod_block']).id('tnp:blaze_rod_block_revert')

});