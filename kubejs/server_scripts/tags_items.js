ServerEvents.tags('item', event => {

  event.add('tnp:any_fire', 'additional_lights:fire_for_standing_torch_s', 'additional_lights:fire_for_standing_torch_l', 'additional_lights:fire_for_fire_pit_s', 'additional_lights:fire_for_fire_pit_l', 'additional_lights:soul_fire_for_standing_torch_s', 'additional_lights:soul_fire_for_standing_torch_l', 'additional_lights:soul_fire_for_fire_pit_s', 'additional_lights:soul_fire_for_fire_pit_l')

  event.add('c:string', 'minecraft:string')

  event.add('c:tools/melee_weapon', 'tnp:limitless_sword')
  event.add('c:tools', 'tnp:limitless_sword')
  event.add('minecraft:swords', 'tnp:limitless_sword')
  event.add('minecraft:enchantable/weapon', 'tnp:limitless_sword')
  event.add('minecraft:enchantable/sword', 'tnp:limitless_sword')
  event.add('minecraft:enchantable/durability', 'tnp:limitless_sword')

  event.add('c:ores/aluminum', 'modern_industrialization:bauxite_ore')
  event.add('c:ores/aluminum', 'modern_industrialization:deepslate_bauxite_ore')

  event.add('c:salts', 'mekanism:salt', 'croptopia:salt', 'refurbished_furniture:sea_salt')

  event.add('c:dusts/yellorium', 'bigreactors:yellorium_dust')
  event.add('c:dusts', 'bigreactors:yellorium_dust')

  event.add('c:dusts/zinc', 'create:zinc_dust')
  event.add('c:dusts', 'create:zinc_dust')

  event.add('c:storage_blocks/raw_yellorium', 'bigreactors:raw_yellorium_block')

  event.add('minecraft:planks', 'deep_aether:roseroot_planks', 'deep_aether:yagroot_planks', 'deep_aether:cruderoot_planks', 'deep_aether:conberry_planks', 'deep_aether:sunroot_planks', 'aether:skyroot_planks')

  event.add('c:coal', 'modern_industrialization:coke')
  event.add('c:coal_coke', 'modern_industrialization:coke')
  event.add('minecraft:coals', 'modern_industrialization:coke')

  event.add('c:dusts/coal_coke', 'modern_industrialization:coke_dust')

  event.add('c:rubbers', 'productivetrees:cured_rubber')

  event.add('c:storage_blocks/coal_coke', 'modern_industrialization:coke_block')
  event.add('c:storage_blocks/coke', 'immersiveengineering:coke')

  event.add('c:foods', 'extradelight:sliced_potato')
  event.add('c:foods/potato', 'extradelight:sliced_potato')
  event.add('c:foods/vegetable', 'extradelight:sliced_potato')

  event.add('c:foods', 'rusticdelight:baked_potato_slices')
  event.add('c:foods/potato', 'rusticdelight:baked_potato_slices')
  event.add('c:foods/vegetable', 'rusticdelight:baked_potato_slices')
  event.add('farmersdelight:cabbage_roll_ingredients', 'rusticdelight:baked_potato_slices')

  event.add('refinedstorage:upgrades', 'refinedstorage:upgrade', 'refinedstorage:speed_upgrade', 'refinedstorage:stack_upgrade', 'refinedstorage:fortune_1_upgrade', 'refinedstorage:fortune_2_upgrade', 'refinedstorage:fortune_3_upgrade', 'refinedstorage:silk_touch_upgrade', 'refinedstorage:regulator_upgrade', 'refinedstorage:range_upgrade', 'refinedstorage:creative_range_upgrade', 'refinedstorage:autocrafting_upgrade')

  event.add('c:stripped_logs', 'integrateddynamics:menril_log_stripped', 'integrateddynamics:menril_wood_stripped')
  event.add('minecraft:logs', 'integrateddynamics:menril_log_stripped', 'integrateddynamics:menril_wood_stripped')

  event.add('c:storage_blocks/blaze_rod', 'tnp:blaze_rod_block')
  event.add('c:storage_blocks/blaze', 'tnp:blaze_rod_block')
  event.add('c:storage_blocks/gunpowder', 'tnp:gunpowder_block')
  event.add('c:storage_blocks', 'tnp:blaze_rod_block', 'tnp:gunpowder_block')

  // Added due to missing tags for unification (not used)
  event.add('c:raw_materials', 'silentgems:raw_silver')
  event.add('c:raw_materials/silver', 'silentgems:raw_silver')

  event.add('getittogetherdrops:do_not_combine', 'minecraft:chorus_fruit')

  event.remove('c:dusts', 'occultism:iron_dust', 'occultism:gold_dust', 'occultism:copper_dust')

  event.remove('c:dusts/iron', 'occultism:iron_dust')
  event.remove('c:dusts/gold', 'occultism:gold_dust')
  event.remove('c:dusts/copper', 'occultism:copper_dust')
  event.remove('c:dusts/coal', 'enderio:powdered_coal')

  event.remove('c:dusts/aluminum', 'moremekanismprocessing:dust_aluminum')
  event.remove('c:dusts/iridium', 'moremekanismprocessing:dust_iridium')
  event.remove('c:dusts/nickel', 'moremekanismprocessing:dust_nickel')
  event.remove('c:dusts/platinum', 'moremekanismprocessing:dust_platinum')
  event.remove('c:dusts/titanium', 'moremekanismprocessing:dust_titanium')
  event.remove('c:dusts/tungsten', 'moremekanismprocessing:dust_tungsten')

  event.remove('c:ingots/aluminum', 'moremekanismprocessing:aluminum_ingot')
  event.remove('c:ingots/iridium', 'moremekanismprocessing:iridium_ingot')
  event.remove('c:ingots/nickel', 'moremekanismprocessing:nickel_ingot')
  event.remove('c:ingots/platinum', 'moremekanismprocessing:platinum_ingot')
  event.remove('c:ingots/titanium', 'moremekanismprocessing:titanium_ingot')
  event.remove('c:ingots/tungsten', 'moremekanismprocessing:tungsten_ingot')

  event.remove('c:nuggets/aluminum', 'moremekanismprocessing:aluminum_nugget')
  event.remove('c:nuggets/iridium', 'moremekanismprocessing:iridium_nugget')
  event.remove('c:nuggets/nickel', 'moremekanismprocessing:nickel_nugget')
  event.remove('c:nuggets/platinum', 'moremekanismprocessing:platinum_nugget')
  event.remove('c:nuggets/titanium', 'moremekanismprocessing:titanium_nugget')
  event.remove('c:nuggets/tungsten', 'moremekanismprocessing:tungsten_nugget')

  event.remove('c:gems/ruby', 'moremekanismprocessing:gem_ruby')
  event.remove('c:gems/peridot', 'moremekanismprocessing:gem_peridot')
  event.remove('c:gems/sapphire', 'moremekanismprocessing:gem_sapphire')

  event.remove('c:ores/redstone', 'regions_unexplored:raw_redstone_block')
  event.remove('minecraft:redstone_ores', 'regions_unexplored:raw_redstone_block')

  event.remove('c:gems/peridot', 'irons_jewelry:peridot')
  event.remove('c:gems/ruby', 'irons_jewelry:ruby')
  event.remove('c:gems/sapphire', 'irons_jewelry:sapphire')
  event.remove('c:gems/topaz', 'irons_jewelry:topaz')

  event.remove('c:ingots/steel', 'oritech:biosteel_ingot')

  event.remove('c:popcorn', 'croptopia:popcorn')
  event.remove('c:foods', 'croptopia:popcorn')
  event.remove('croptopia:advancements_food_crafted', 'croptopia:popcorn')

  event.remove('tombstone:lootable/armor', 'tnp:limitless_helmet')
  event.remove('kobolds:kobold_armor', 'tnp:limitless_helmet')

  // Nugget tags removed for DnD Lapis Lazuli Shard.
  event.remove('c:nuggets', 'dndesires:lapis_lazuli_shard')
  event.remove('c:nuggets/lapis', 'dndesires:lapis_lazuli_shard')

  // Ores tag to custom Deepslate Black Quartz Ore
  event.add('c:ores', 'actuallyadditions:deepslate_black_quartz_ore')
  event.add('c:ores/black_quartz', 'actuallyadditions:deepslate_black_quartz_ore')

  // Ores tag to custom Deepslate Platinum Ore
  event.add('c:ores', 'modern_industrialization:deepslate_platinum_ore')
  event.add('c:ores/platinum', 'modern_industrialization:deepslate_platinum_ore')

  // Relics to Artifacts tag for recipe purposes (Salvager)
  event.add('artifacts:artifacts', 'relics:reflection_necklace', 'relics:magma_walker', 'relics:aqua_walker', 'relics:midnight_robe', 'relics:drowned_belt', 'relics:jellyfish_necklace', 'relics:hunter_belt', 'relics:rage_glove', 'relics:ice_skates', 'relics:bastion_ring', 'relics:chorus_inhibitor', 'relics:space_dissector', 'relics:holy_locket', 'relics:enders_hand', 'relics:elytra_booster', 'relics:magic_mirror', 'relics:ice_breaker', 'relics:blazing_flask', 'relics:spore_sack', 'relics:shadow_glaive', 'relics:roller_skates', 'relics:infinity_ham', 'relics:leather_belt', 'relics:wool_mitten', 'relics:amphibian_boot', 'relics:leafy_ring', 'relics:phantom_boot', 'relics:springy_boot', 'relics:solid_snowball', 'relics:relic_experience_bottle', 'relicsofrain:bustling_fungus', 'relicsofrain:soldier_syringe', 'relicsofrain:energy_drink', 'relicsofrain:ukulele', 'relicsofrain:frost_relic', 'relicsofrain:platinum_horseshoe', 'relicsofrain:broken_mirror', 'relicsofrain:unlabeled_syringe', 'relicsofrain:wax_quail', 'relicsofrain:katana_trinket', 'relicsofrain:radiant_pearl')

  // Added direthings upgrades to tags for quest use.
  event.add('justdirethings:upgrades', 'justdirethings:upgrade_mobscanner', 'justdirethings:upgrade_oreminer', 'justdirethings:upgrade_orescanner', 'justdirethings:upgrade_lawnmower', 'justdirethings:upgrade_skysweeper', 'justdirethings:upgrade_treefeller', 'justdirethings:upgrade_leafbreaker', 'justdirethings:upgrade_runspeed', 'justdirethings:upgrade_walkspeed', 'justdirethings:upgrade_stepheight', 'justdirethings:upgrade_jumpboost', 'justdirethings:upgrade_mindfog', 'justdirethings:upgrade_invulnerability', 'justdirethings:upgrade_potionarrow', 'justdirethings:upgrade_smelter', 'justdirethings:upgrade_smoker', 'justdirethings:upgrade_hammer', 'justdirethings:upgrade_cauterizewounds', 'justdirethings:upgrade_swimspeed', 'justdirethings:upgrade_groundstomp', 'justdirethings:upgrade_extinguish', 'justdirethings:upgrade_splash', 'justdirethings:upgrade_elytra', 'justdirethings:upgrade_dropteleport', 'justdirethings:upgrade_negatefalldamage', 'justdirethings:upgrade_nightvision', 'justdirethings:upgrade_decoy', 'justdirethings:upgrade_lingering', 'justdirethings:upgrade_homing', 'justdirethings:upgrade_waterbreathing', 'justdirethings:upgrade_orexray', 'justdirethings:upgrade_stupefy', 'justdirethings:upgrade_glowing', 'justdirethings:upgrade_instabreak', 'justdirethings:upgrade_earthquake', 'justdirethings:upgrade_noai', 'justdirethings:upgrade_flight', 'justdirethings:upgrade_phase', 'justdirethings:upgrade_deathprotection', 'justdirethings:upgrade_lavaimmunity', 'justdirethings:upgrade_debuffremover', 'justdirethings:upgrade_epicarrow', 'justdirethings:upgrade_time_protection')

  // Nugget tags for Lapis Shard.
  event.add('c:nuggets', 'solargeneration:lapis_shard')
  event.add('c:nuggets/lapis', 'solargeneration:lapis_shard')

  // Improved mod compatibility
  event.add('c:fruits', 'tropicraft:coconut', 'tropicraft:passionfruit', 'croptopia:grapefruit', 'tropicraft:grapefruit', 'tropicraft:lemon', 'tropicraft:lime', 'tropicraft:orange', 'tropicraft:papaya', 'tropicraft:yellow_plantain', 'tropicraft:jocote', 'tropicraft:dried_plantains', 'tropicraft:green_plantain')
  event.add('c:foods/fruits', 'tropicraft:passionfruit', 'croptopia:grapefruit', 'tropicraft:grapefruit', 'tropicraft:lemon', 'tropicraft:lime', 'tropicraft:orange', 'tropicraft:papaya', 'tropicraft:yellow_plantain', 'tropicraft:jocote', 'tropicraft:dried_plantains', 'tropicraft:green_plantain')
  event.add('c:foods', 'tropicraft:passionfruit', 'croptopia:grapefruit', 'tropicraft:grapefruit', 'tropicraft:lemon', 'tropicraft:lime', 'tropicraft:orange', 'tropicraft:papaya', 'tropicraft:yellow_plantain', 'tropicraft:jocote', 'tropicraft:dried_plantains', 'tropicraft:green_plantain')
  event.add('c:crops', 'tropicraft:coconut', 'tropicraft:passionfruit', 'croptopia:grapefruit', 'tropicraft:grapefruit', 'tropicraft:lemon', 'tropicraft:lime', 'tropicraft:orange', 'tropicraft:papaya', 'tropicraft:yellow_plantain', 'tropicraft:jocote', 'tropicraft:dried_plantains', 'tropicraft:green_plantain')
  event.add('c:fruits/grapefruit', 'croptopia:grapefruit', 'tropicraft:grapefruit')
  event.add('c:fruits/passionfruit', 'tropicraft:passionfruit')
  event.add('c:fruits/lemon', 'tropicraft:lemon')
  event.add('c:fruits/lime', 'tropicraft:lime')
  event.add('c:fruits/orange', 'tropicraft:orange')
  event.add('c:fruits/papaya', 'tropicraft:papaya')
  event.add('c:fruits/plantain', 'tropicraft:yellow_plantain', 'tropicraft:green_plantain', 'tropicraft:dried_plantains')
  event.add('c:fruits/jocote', 'tropicraft:jocote')
  event.add('c:crops/coconut', 'tropicraft:coconut')
  event.add('c:crops/grapefruit', 'croptopia:grapefruit', 'tropicraft:grapefruit')
  event.add('c:crops/passionfruit', 'tropicraft:passionfruit')
  event.add('c:crops/lemon', 'tropicraft:lemon')
  event.add('c:crops/lime', 'tropicraft:lime')
  event.add('c:crops/orange', 'tropicraft:orange')
  event.add('c:crops/papaya', 'tropicraft:papaya')
  event.add('c:crops/plantain', 'tropicraft:yellow_plantain', 'tropicraft:green_plantain', 'tropicraft:dried_plantains')
  event.add('c:crops/jocote', 'tropicraft:jocote')
  event.add('c:nuts', 'tropicraft:mahogany_nut', 'tropicraft:coconut')
  event.add('c:coconuts', 'tropicraft:coconut')

  event.add('crabbersdelight:cooked_seafood', 'croptopia:steamed_clams', 'croptopia:steamed_crab', 'croptopia:cooked_shrimp', 'croptopia:deep_fried_shrimp')

  event.add('crabbersdelight:raw_seafood', 'croptopia:clam', 'croptopia:crab', 'croptopia:shrimp')

  event.add('c:crabs', 'crabbersdelight:raw_crab')
  event.add('c:shrimp', 'crabbersdelight:raw_shrimp')
  event.add('c:clams', 'crabbersdelight:raw_clam_meat', 'crabbersdelight:clam')

  event.add('c:steamed_crabs', 'crabbersdelight:cooked_crab')
  event.add('c:cooked_shrimp', 'crabbersdelight:cooked_shrimp')
  event.add('c:steamed_clams', 'crabbersdelight:cooked_clam_meat')

  event.add('c:plastics', 'pneumaticcraft:plastic', 'immersiveengineering:plate_duroplast')
  event.add('pneumaticcraft:plastic_sheets', 'immersiveengineering:plate_duroplast', 'industrialforegoing:plastic')
  event.add('c:plates/plastic', 'industrialforegoing:plastic', 'pneumaticcraft:plastic')

});