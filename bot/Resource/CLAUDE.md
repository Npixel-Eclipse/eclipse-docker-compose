# Eclipse Game Resources (YAML Configuration System)

## Overview

- **Purpose**: Centralized game configuration data (items, skills, NPCs, quests, etc.)
- **Format**: YAML files with JSON schema validation
- **Usage**: Loaded by services at startup into `ResourceContainer` (HashMap)
- **Editing**: Use DataTool (`Deploy/DataTool/datatool.exe`) for schema-validated editing

## Resource Architecture

### Data Flow

```
YAML Files (Resource/)
    ↓ (Load at startup)
ResourceContainer (HashMap<ID, Resource>)
    ↓ (Query at runtime)
Service Logic (Battle, Item, Quest, etc.)
    ↓ (Send via Kafka/Protobuf)
Client (UE5)
```

### Key Principles

1. **Master Data**: YAML files are the source of truth for game content
2. **Schema Validation**: Every `.yaml` has a corresponding `.schema.yaml` (JSON Schema format)
3. **Cross-References**: Resources reference each other via IDs (e.g., skill.yaml → buff.yaml)
4. **Versioning**: Use Perforce for version control, track changes carefully
5. **No Runtime Modification**: Resources are read-only after loading (restart required for changes)

## Core Resources

### Combat System

#### skill.yaml (Skill Definitions)
**Size**: ~500 KB | **Records**: 1,000+ skills

**Structure**:
```yaml
- skill_id: 1001
  name: "Fireball"
  desc_id: 10001  # References description.yaml
  type: "OFFENSIVE"
  cooldown: 5.0
  mana_cost: 50
  range: 20.0
  effects:
    - type: "DAMAGE"
      value: 500
      property_id: 101  # References property.yaml (ATK)
    - type: "APPLY_BUFF"
      buff_id: 201  # References buff.yaml
      duration: 3.0
  animation_id: "skill_fireball"
```

**Used By**: Battle server (skill execution), Client (UI, animations)

#### buff.yaml (Buff/Debuff Effects)
**Size**: ~300 KB | **Records**: 500+ buffs

**Structure**:
```yaml
- buff_id: 201
  name: "Burn"
  desc_id: 20001
  type: "DEBUFF"
  duration: 3.0
  max_stacks: 3
  tick_interval: 1.0
  properties:
    - property_id: 101  # ATK reduction
      operator: "ADD"
      value: -50
    - property_id: 105  # HP drain per tick
      operator: "ADD"
      value: -30
  icon: "buff_burn"
  removable: true  # Can be cleansed
```

**Special Buff #44**: Hardcoded "property transport buff" (no visible icon). Used to send stat changes (equipment, passive effects) from services to battle/client without showing buff UI.

**Used By**: Battle server (buff system), Client (buff icons)

#### property.yaml (Stat Definitions - Shared Enum)
**Size**: ~10 KB | **Records**: 50+ properties

**Structure**:
```yaml
- property_id: 101
  name: "ATK"
  desc_id: 30001
  type: "STAT"
  default_value: 0
  min_value: 0
  max_value: 99999

- property_id: 102
  name: "DEF"
  desc_id: 30002
  type: "STAT"
  default_value: 0
  min_value: 0
  max_value: 99999
```

**Critical**: This is a **shared enum** used by:
- buff.yaml (stat modifiers)
- skill.yaml (damage/heal calculations)
- stat.yaml (stat formulas)
- formula.yaml (damage formulas)
- Battle server (PropertyBag component)

**⚠️ Changing property.yaml affects EVERYTHING. Test thoroughly.**

**Used By**: All services, battle server, client

### Item System

#### item.yaml (Item Master Data)
**Size**: ~4.3 MB | **Records**: 10,000+ items

**Structure**:
```yaml
- item_id: 5001
  name_id: 50001  # References description.yaml
  desc_id: 50002
  type: "EQUIPMENT"
  subtype: "WEAPON"
  rarity: "EPIC"
  level_requirement: 50
  class_requirement: ["WARRIOR", "KNIGHT"]
  stats:
    - property_id: 101  # ATK
      value: 300
    - property_id: 103  # CRIT
      value: 15
  tradeable: true
  stack_size: 1
  icon: "weapon_sword_epic_01"
```

**Used By**: Item service (inventory), battle server (equipment stats), client (UI)

#### item_display.yaml (Item UI Configuration)
**Size**: ~100 KB | **Records**: 10,000+ display settings

**Structure**:
```yaml
- item_id: 5001
  icon: "weapon_sword_epic_01"
  model: "SM_Sword_Epic_01"
  color_grade: "#FF9D00"  # Epic orange
  glow_effect: true
```

**Used By**: Client (item rendering, UI)

### NPC & AI System

#### npc.yaml (NPC Definitions)
**Size**: ~1 MB | **Records**: 2,000+ NPCs

**Structure**:
```yaml
- npc_id: 523
  name_id: 52301
  type: "MONSTER"
  level: 50
  ai_behavior_tree_id: 42  # References ai.yaml
  stats:
    - property_id: 105  # HP
      value: 50000
    - property_id: 101  # ATK
      value: 500
  skills: [1001, 1002, 1003]  # References skill.yaml
  drops:
    - item_id: 5001  # References item.yaml
      drop_rate: 0.05
      min_quantity: 1
      max_quantity: 1
```

**Used By**: Battle server (NPC spawning, combat, AI)

#### ai.yaml (AI Behavior Trees)
**Size**: ~350 KB | **Records**: 100+ behavior trees

**Structure**:
```yaml
- behavior_tree_id: 42
  name: "Aggressive Melee"
  root:
    type: "SELECTOR"  # Try children in order until one succeeds
    children:
      - type: "SEQUENCE"  # Combat sequence
        children:
          - type: "CONDITION"
            condition: "InCombat"
          - type: "ACTION"
            action: "SelectTarget"
          - type: "ACTION"
            action: "MoveToTarget"
            params:
              min_distance: 2.0
          - type: "ACTION"
            action: "UseSkill"
            params:
              skill_id: 1001
      - type: "ACTION"  # Idle/patrol
        action: "Patrol"
```

**Node Types**:
- **SELECTOR**: Try children until one succeeds (OR logic)
- **SEQUENCE**: Execute children in order, fail if any fails (AND logic)
- **CONDITION**: Evaluate boolean condition (InCombat, HealthBelow, etc.)
- **ACTION**: Execute action (MoveToTarget, UseSkill, Patrol, etc.)

**Used By**: Battle server (AI system)

#### npc_spawn.yaml (Spawn Locations)
**Size**: ~200 KB | **Records**: 5,000+ spawn points

**Structure**:
```yaml
- spawn_id: 1001
  npc_id: 523  # References npc.yaml
  zone_id: 101  # References zone.yaml
  position:
    x: 1000.0
    y: 500.0
    z: 0.0
  respawn_time: 60.0  # Seconds
  schedule:
    - start_time: "00:00:00"
      end_time: "23:59:59"
      active: true
```

**Used By**: Battle server (NPC spawning)

### Localization

#### description.yaml (All UI Text)
**Size**: ~6.9 MB | **Records**: 50,000+ text entries

**Structure**:
```yaml
- desc_id: 10001
  ko: "화염구"
  en: "Fireball"

- desc_id: 10002
  ko: "적에게 화염 피해를 입힙니다."
  en: "Deals fire damage to an enemy."
```

**Languages**: Currently Korean (`ko`) and English (`en`)

**Used By**: All services, client (UI text)

### Client Integration

#### client_constants.yaml (Client-Side Mappings)
**Size**: ~50 KB | **Records**: 1,000+ constants

**Structure**:
```yaml
skill_icon_mapping:
  - skill_id: 1001
    icon_path: "/Game/UI/Icons/Skills/Fireball"
    animation_path: "/Game/Animations/Skills/Fireball"

ui_constants:
  max_inventory_slots: 100
  max_skill_slots: 10
```

**Important**: When adding new skills, update BOTH `skill.yaml` AND `client_constants.yaml`

**Used By**: Client (UI, animations, game rules)

## Schema Validation

### Schema Files

Every `.yaml` has a `.schema.yaml` (JSON Schema format):

```yaml
# skill.schema.yaml
type: array
items:
  type: object
  required: [skill_id, name, type]
  properties:
    skill_id:
      type: integer
      minimum: 1
    name:
      type: string
      minLength: 1
    cooldown:
      type: number
      minimum: 0
```

### Validation Workflow

1. **Edit YAML**: Use DataTool (recommended) or text editor
2. **Validate**: DataTool auto-validates against schema
3. **Manual Validation**: Run `Resource/_generate_json.bat` (generates JSON for services)
4. **Test Locally**: Use `run-all-local-servers` skill to test changes
5. **Check Logs**: Use `read-game-server-log` skill for loading errors

### Common Validation Errors

#### Missing Required Field
```
Error: skill.yaml[42] missing required field 'skill_id'
Fix: Add skill_id field
```

#### Type Mismatch
```
Error: buff.yaml[10] field 'duration' expected number, got string
Fix: Change "3.0" to 3.0 (remove quotes)
```

#### Invalid Reference
```
Error: skill.yaml[5] references buff_id 999 but buff not found in buff.yaml
Fix: Either add buff #999 to buff.yaml or correct the reference
```

## Common Workflows

### Adding a New Item

1. **Edit item.yaml**: Add item definition
```yaml
- item_id: 6001
  name_id: 60001
  type: "EQUIPMENT"
  stats:
    - property_id: 101  # ATK
      value: 500
```

2. **Edit description.yaml**: Add Korean and English text
```yaml
- desc_id: 60001
  ko: "전설의 검"
  en: "Legendary Sword"
```

3. **Edit item_display.yaml**: Add UI display settings
```yaml
- item_id: 6001
  icon: "weapon_legendary_sword"
  model: "SM_Legendary_Sword"
```

4. **Validate**: Run `_generate_json.bat` or use DataTool

5. **Test**: Use `run-all-local-servers` + game client

6. **p4 edit**: Open files for editing in Perforce
```bash
p4 edit Resource/item.yaml Resource/description.yaml Resource/item_display.yaml
```

### Adding a New Skill with Buff

1. **Edit buff.yaml**: Add buff effect
```yaml
- buff_id: 301
  name: "Stun"
  duration: 2.0
  properties:
    - property_id: 120  # MOVEMENT_SPEED
      operator: "MULTIPLY"
      value: 0  # Completely stop movement
```

2. **Edit skill.yaml**: Add skill that applies buff
```yaml
- skill_id: 2001
  name: "Stunning Strike"
  effects:
    - type: "APPLY_BUFF"
      buff_id: 301
      target: "ENEMY"
```

3. **Edit description.yaml**: Add text for both
```yaml
- desc_id: 30001
  ko: "기절"
  en: "Stun"

- desc_id: 20001
  ko: "적을 기절시킵니다"
  en: "Stuns the enemy"
```

4. **Edit client_constants.yaml**: Add UI mapping
```yaml
skill_icon_mapping:
  - skill_id: 2001
    icon_path: "/Game/UI/Icons/Skills/StunningStrike"
```

5. **Validate and test**

### Modifying NPC AI

1. **Find NPC** in `npc.yaml`: Get `ai_behavior_tree_id`

2. **Edit ai.yaml**: Modify behavior tree
```yaml
- behavior_tree_id: 42
  root:
    type: "SELECTOR"
    children:
      - type: "SEQUENCE"
        children:
          - type: "CONDITION"
            condition: "HealthBelow"
            params:
              threshold: 0.3  # Flee when HP < 30%
          - type: "ACTION"
            action: "Flee"
```

3. **Test**: Spawn NPC in game, verify AI behavior

4. **p4 edit**: `p4 edit Resource/ai.yaml`

## Cross-Reference Patterns

### Common References

- `item.yaml` → `description.yaml` (name_id, desc_id)
- `item.yaml` → `property.yaml` (stats)
- `skill.yaml` → `buff.yaml` (effects)
- `skill.yaml` → `property.yaml` (damage calculations)
- `skill.yaml` → `description.yaml` (name, description)
- `npc.yaml` → `ai.yaml` (ai_behavior_tree_id)
- `npc.yaml` → `skill.yaml` (NPC skills)
- `npc.yaml` → `item.yaml` (loot drops)
- `buff.yaml` → `property.yaml` (stat modifiers)

### Validation

Always verify references exist:
```bash
# Check if buff_id 301 exists
grep "buff_id: 301" Resource/buff.yaml

# Check if property_id 101 exists
grep "property_id: 101" Resource/property.yaml
```

## Impact Analysis

### Changing Resources → Service Impact

| Resource Changed | Affected Services | Restart Required |
|-----------------|-------------------|------------------|
| `item.yaml` | item, battle, quest, client | ✅ All |
| `skill.yaml` | battle, client | ✅ Battle + Client |
| `buff.yaml` | battle, client | ✅ Battle + Client |
| `property.yaml` | **ALL SERVICES** | ✅ **EVERYTHING** |
| `ai.yaml` | battle | ✅ Battle only |
| `npc.yaml` | battle | ✅ Battle only |
| `description.yaml` | client | ✅ Client only |
| `client_constants.yaml` | client | ✅ Client only |

### Testing Checklist

Before submitting YAML changes:
- [ ] Schema validation passed (`_generate_json.bat` no errors)
- [ ] Cross-references verified (all IDs exist)
- [ ] Tested locally with `run-all-local-servers`
- [ ] Tested in-game (spawn item, use skill, fight NPC, etc.)
- [ ] Checked logs for loading errors
- [ ] Reviewed impact (which services need restart)
- [ ] Updated related YAML files (description.yaml, client_constants.yaml)

## Tools

### DataTool (Recommended)
**Path**: `F:\Work\Eclipse\Deploy\DataTool\datatool.exe`

**Features**:
- Schema-validated editing
- Auto-complete for enums
- Cross-reference validation
- Syntax highlighting
- Search and filter

**Usage**:
1. Open DataTool
2. Select resource file (e.g., item.yaml)
3. Edit fields with validation
4. Save (auto-validates)

### Manual Editing

**Text Editor**: VS Code, Sublime, Notepad++

**Validation**:
```bash
cd Resource
_generate_json.bat
# Check for errors in output
```

## Troubleshooting

### Resource Loading Failed

**Symptom**: Service fails to start, logs show "Failed to load resource"

**Causes**:
- YAML syntax error (invalid indentation, missing colon)
- Schema validation failed (missing required field, type mismatch)
- Cross-reference broken (references non-existent ID)
- File encoding issue (must be UTF-8)

**Solution**:
```bash
# Check YAML syntax
yamllint Resource/item.yaml

# Validate against schema
_generate_json.bat

# Check encoding
file -i Resource/item.yaml  # Should show charset=utf-8

# Check logs
read-game-server-log → Search for "resource" errors
```

### Cross-Reference Errors

**Symptom**: Service loads but runtime errors occur ("Buff not found", "Skill not found")

**Causes**:
- Referenced ID doesn't exist (typo, deleted, wrong file)
- ID type mismatch (buff_id as string instead of integer)

**Solution**:
```bash
# Find all references to buff_id 301
grep -r "buff_id.*301" Resource/

# Verify buff exists
grep "buff_id: 301" Resource/buff.yaml
```

### Property.yaml Changes Breaking Everything

**Symptom**: Multiple services fail after property.yaml change

**Cause**: property.yaml is a shared enum, changes affect:
- buff.yaml (stat modifiers)
- skill.yaml (damage calculations)
- Battle server (PropertyBag)
- Client (stat UI)

**Solution**:
- **Don't delete properties**: Mark as deprecated instead
- **Don't change property_id**: Add new property instead
- **Test exhaustively**: All services, all scenarios
- **Coordinate deployment**: Deploy all services simultaneously

## Performance Considerations

- **Startup Time**: Large YAML files (description.yaml 6.9MB) slow startup
- **Memory Usage**: All resources loaded into memory (HashMap)
- **No Caching**: Resources never modified at runtime (no cache invalidation needed)
- **Optimization**: Consider splitting large files (e.g., description.yaml by language)

## Related Documentation

- **Resource Expert**: `.claude/agents/resource-expert.md`
- **Battle Server**: `Source/battle/CLAUDE.md`
- **Backend Services**: `.claude/agents/backend-server-dev.md`
- **DataTool Manual**: `Deploy/DataTool/README.md`

---

**Last Updated**: 2025-10-27
**Maintainer**: Game Design + Backend Team
**Resource Status**: Production
