# Eclipse Protocol Definitions (Protobuf)

## Overview

- **Purpose**: Define message formats for client-server and inter-service communication
- **Format**: Protocol Buffers (protobuf) v3
- **Usage**: Code generation for Kotlin (services), Rust (battle), C++ (client)
- **Architecture**: Three communication layers (Client, Front, Server)

## Protocol Architecture

### Communication Layers

```
┌─────────────────────────────────────────────────┐
│                   Client (UE5)                   │
└───────────┬─────────────────────┬────────────────┘
            │                     │
            │ WebSocket           │ WebSocket
            │ (Proto/Client)      │ (Proto/Front)
            ↓                     ↓
┌───────────────────┐   ┌──────────────────────┐
│   Lobby Service   │   │   Front Service      │
└─────────┬─────────┘   └──────────┬───────────┘
          │                        │
          │ gRPC (Proto/Server)    │ gRPC
          ↓                        ↓
┌──────────────────────────────────────────────┐
│      Backend Services (Item, Guild, etc.)    │
│            + Battle Server (Rust)             │
└──────────────────────────────────────────────┘
          ↓                        ↑
          Kafka Events (Proto/Server/Events)
```

### Directory Structure

```
Proto/
├── Client/           # Client → Lobby WebSocket messages
│   ├── login.proto
│   ├── character.proto
│   └── ...
├── Front/            # Client → Front → Battle WebSocket messages
│   ├── movement.proto
│   ├── skill.proto
│   ├── combat.proto
│   └── ...
├── Server/           # Inter-service communication (gRPC + Kafka)
│   ├── Item/
│   ├── Guild/
│   ├── Battle/
│   ├── Common/
│   └── Events/
└── Common/           # Shared types across all protocols
    ├── types.proto
    └── enums.proto
```

## Protocol Layers Explained

### 1. Proto/Client/ (Lobby Layer)

**Purpose**: Authentication, lobby features, non-combat interactions

**Transport**: WebSocket (binary protobuf)

**Messages**:
- **Login/Logout**: Authentication, session management
- **Character**: Character creation, selection, deletion
- **Inventory**: Item management (non-combat)
- **Guild**: Guild operations (create, join, chat)
- **Mail**: In-game mail
- **Store**: Shop purchases

**Example** (`Client/login.proto`):
```protobuf
syntax = "proto3";

package eclipse.client;

message LoginRequest {
  string username = 1;
  string password = 2;  // Or token
  string client_version = 3;
}

message LoginResponse {
  enum Result {
    SUCCESS = 0;
    INVALID_CREDENTIALS = 1;
    ALREADY_LOGGED_IN = 2;
    MAINTENANCE = 3;
    BANNED = 4;
  }

  Result result = 1;
  string session_token = 2;
  int64 player_id = 3;
  repeated Character characters = 4;
}
```

**Code Generation**:
```bash
# Kotlin (Lobby service)
protoc --java_out=Source/lobby/src/main/java Proto/Client/*.proto

# C++ (UE5 Client)
protoc --cpp_out=ProjectX/Source/Proto Proto/Client/*.proto
```

### 2. Proto/Front/ (Battle Layer)

**Purpose**: Real-time combat, movement, skills, NPC interactions

**Transport**: WebSocket (binary protobuf)

**Messages**:
- **Movement**: Player movement, rotation
- **Combat**: Damage events, death
- **Skill**: Skill usage, cooldowns
- **Buff**: Buff application, removal
- **NPC**: NPC spawning, AI state
- **Loot**: Item drops, looting

**Example** (`Front/skill.proto`):
```protobuf
syntax = "proto3";

package eclipse.front;

message UseSkillRequest {
  int32 skill_id = 1;
  int64 target_entity_id = 2;  // 0 for self-cast
  Vector3 target_position = 3;  // For ground-targeted skills
}

message SkillUsedEvent {
  int64 caster_entity_id = 1;
  int32 skill_id = 2;
  int64 target_entity_id = 3;
  bool success = 4;
  string failure_reason = 5;  // "ON_COOLDOWN", "NOT_ENOUGH_MANA", etc.
}

message SkillDamageEvent {
  int64 caster_entity_id = 1;
  int64 target_entity_id = 2;
  int32 skill_id = 3;
  int32 damage = 4;
  bool is_critical = 5;
  repeated int32 buff_ids_applied = 6;
}
```

**Code Generation**:
```bash
# Rust (Battle server)
protoc --rust_out=Source/battle/src/proto Proto/Front/*.proto

# C++ (UE5 Client)
protoc --cpp_out=ProjectX/Source/Proto Proto/Front/*.proto
```

### 3. Proto/Server/ (Inter-Service Layer)

**Purpose**: Backend microservice communication (gRPC + Kafka events)

**Transport**:
- **gRPC**: Synchronous service-to-service calls
- **Kafka**: Asynchronous event streaming

**Subdirectories**:
- `Server/Item/`: Item service gRPC APIs
- `Server/Guild/`: Guild service gRPC APIs
- `Server/Battle/`: Battle server Kafka commands
- `Server/Common/`: Shared service types
- `Server/Events/`: Kafka event definitions

**Example** (`Server/Item/item_service.proto`):
```protobuf
syntax = "proto3";

package eclipse.server.item;

service ItemService {
  rpc GetInventory(GetInventoryRequest) returns (GetInventoryResponse);
  rpc EquipItem(EquipItemRequest) returns (EquipItemResponse);
  rpc UseItem(UseItemRequest) returns (UseItemResponse);
}

message GetInventoryRequest {
  int64 player_id = 1;
  int32 page = 2;
  int32 page_size = 3;
}

message GetInventoryResponse {
  repeated ItemInstance items = 1;
  int32 total_count = 2;
}

message ItemInstance {
  int64 item_instance_id = 1;
  int32 item_id = 2;  // References Resource/item.yaml
  int32 quantity = 3;
  int32 enhancement_level = 4;
  map<string, string> metadata = 5;
}
```

**Example** (`Server/Events/item_events.proto`):
```protobuf
syntax = "proto3";

package eclipse.server.events;

// Published to Kafka topic: item.acquired
message ItemAcquiredEvent {
  int64 player_id = 1;
  int32 item_id = 2;
  int32 quantity = 3;
  string source = 4;  // "QUEST", "SHOP", "BATTLE_DROP", "MAIL"
  int64 timestamp = 5;
}

// Published to Kafka topic: item.equipped
message ItemEquippedEvent {
  int64 player_id = 1;
  int64 item_instance_id = 2;
  string slot = 3;  // "WEAPON", "ARMOR", "ACCESSORY"
  repeated PropertyChange stat_changes = 4;
  int64 timestamp = 5;
}

message PropertyChange {
  int32 property_id = 1;  // References Resource/property.yaml
  int32 old_value = 2;
  int32 new_value = 3;
}
```

**Code Generation**:
```bash
# Kotlin (all backend services)
cd Source/item
./gradlew generateProto  # Generates Java/Kotlin code

# Rust (battle server)
cd Source/battle
cargo build  # build.rs handles protoc codegen
```

### 4. Proto/Common/ (Shared Types)

**Purpose**: Types used across multiple protocol layers

**Examples**:
- `Vector3`: Position (x, y, z)
- `Timestamp`: Unix timestamp
- `EntityType`: Enum (PC, NPC, ITEM, etc.)
- `Result`: Generic result codes

**Example** (`Common/types.proto`):
```protobuf
syntax = "proto3";

package eclipse.common;

message Vector3 {
  float x = 1;
  float y = 2;
  float z = 3;
}

message Rotation {
  float yaw = 1;
  float pitch = 2;
  float roll = 3;
}

enum EntityType {
  ENTITY_TYPE_UNSPECIFIED = 0;
  PC = 1;
  NPC = 2;
  DROP_ITEM = 3;
  PROJECTILE = 4;
  BUFF = 5;
}
```

## Code Generation Workflow

### Adding/Modifying a Message

1. **Edit .proto file**: Modify message definition

2. **Regenerate code**:

**Kotlin services**:
```bash
cd Source/{service}
./gradlew generateProto
# Generated code: build/generated/source/proto/main/java/
```

**Rust battle server**:
```bash
cd Source/battle
cargo build
# build.rs automatically runs protoc
# Generated code: target/debug/build/battle-*/out/
```

**C++ client**:
```bash
cd ProjectX
# Run UE5 build (or manual protoc)
protoc --cpp_out=Source/Proto Proto/**/*.proto
```

3. **p4 edit**: Open files for editing
```bash
p4 edit Proto/Server/Item/item_service.proto
```

4. **Rebuild affected services**:
```bash
# Rebuild item service
cd Source/item
./gradlew build

# Rebuild battle server
cd Source/battle
cargo build

# Rebuild client
cd ProjectX
# Use UE5 editor or command line build
```

5. **Test**: Run local servers and client

## Common Patterns

### Request-Response (gRPC)

**Pattern**: Synchronous service call

**Example**:
```protobuf
service ItemService {
  rpc GetInventory(GetInventoryRequest) returns (GetInventoryResponse);
}
```

**Usage** (Kotlin):
```kotlin
val response = itemServiceStub.getInventory(
    GetInventoryRequest.newBuilder()
        .setPlayerId(playerId)
        .build()
)
```

### Event Publishing (Kafka)

**Pattern**: Asynchronous event notification

**Example**:
```protobuf
message ItemAcquiredEvent {
  int64 player_id = 1;
  int32 item_id = 2;
  int32 quantity = 3;
}
```

**Usage** (Kotlin):
```kotlin
streamBridge.send("item-acquired",
    ItemAcquiredEvent.newBuilder()
        .setPlayerId(playerId)
        .setItemId(itemId)
        .setQuantity(quantity)
        .build()
)
```

### Bidirectional Streaming (WebSocket)

**Pattern**: Continuous client-server communication

**Example**:
```protobuf
message MovementUpdate {
  int64 entity_id = 1;
  Vector3 position = 2;
  Rotation rotation = 3;
  float velocity = 4;
}
```

**Usage** (Battle server → Client):
```rust
// Serialize protobuf
let update = MovementUpdate {
    entity_id: entity.id,
    position: Some(entity.position.to_proto()),
    rotation: Some(entity.rotation.to_proto()),
    velocity: entity.velocity,
};
let bytes = update.encode_to_vec();

// Send via WebSocket
websocket.send(bytes).await?;
```

## Versioning and Compatibility

### Protobuf Versioning Rules

**✅ Backward-Compatible Changes**:
- Add new fields (clients can ignore unknown fields)
- Add new message types
- Add new enum values (with `UNSPECIFIED = 0`)

**❌ Breaking Changes**:
- Remove fields (clients will break)
- Change field types (serialization breaks)
- Change field numbers (wire format changes)
- Remove enum values (clients using old enums break)

### Deprecation Pattern

Instead of removing fields, mark as deprecated:

```protobuf
message OldMessage {
  int32 old_field = 1 [deprecated = true];  // Don't use anymore
  int32 new_field = 2;  // Use this instead
}
```

### Version Checking

Client sends version in LoginRequest:
```protobuf
message LoginRequest {
  string client_version = 3;  // "1.2.3"
}
```

Server validates:
```kotlin
if (request.clientVersion < minSupportedVersion) {
    return LoginResponse.newBuilder()
        .setResult(Result.VERSION_MISMATCH)
        .build()
}
```

## Testing Protocols

### Unit Testing (Kotlin)

```kotlin
@Test
fun `test ItemAcquiredEvent serialization`() {
    val event = ItemAcquiredEvent.newBuilder()
        .setPlayerId(123)
        .setItemId(456)
        .setQuantity(10)
        .build()

    val bytes = event.toByteArray()
    val parsed = ItemAcquiredEvent.parseFrom(bytes)

    assertEquals(123, parsed.playerId)
    assertEquals(456, parsed.itemId)
    assertEquals(10, parsed.quantity)
}
```

### Integration Testing (Kafka)

```kotlin
@SpringBootTest
@EmbeddedKafka
class ItemEventIntegrationTest {
    @Test
    fun `test item acquired event consumed`() {
        // Publish event
        streamBridge.send("item-acquired", event)

        // Verify consumed
        await().atMost(5, SECONDS).until {
            questService.wasEventReceived(event)
        }
    }
}
```

### Client-Server Testing (Battle)

Use cheat commands to trigger events:
```
/give_item 456 10  # Triggers ItemAcquiredEvent
/equip_item 789    # Triggers ItemEquippedEvent
```

Monitor logs to verify protobuf serialization.

## Troubleshooting

### Deserialization Failed

**Symptom**: "Failed to parse protobuf message"

**Causes**:
- Client and server using different .proto versions
- Field number mismatch
- Required field missing (protobuf v2 only, v3 has no required)
- Corrupted message (network issue)

**Solution**:
```bash
# Verify protoc versions match
protoc --version  # Should be same on all machines

# Check .proto file field numbers
grep "= 1;" Proto/Server/Item/item_service.proto

# Regenerate code
./gradlew generateProto  # Kotlin
cargo clean && cargo build  # Rust
```

### gRPC Connection Timeout

**Symptom**: "Deadline exceeded" when calling service

**Causes**:
- Target service not running
- Network issue (firewall, DNS)
- Service overloaded (high latency)

**Solution**:
```bash
# Check service health
curl http://item-service:8080/actuator/health

# Check gRPC port open
telnet item-service 9090

# Increase timeout
stub.withDeadlineAfter(10, SECONDS).getInventory(request)
```

### Kafka Event Not Consumed

**Symptom**: Event published but not consumed by target service

**Causes**:
- Topic name mismatch (typo)
- Consumer group not configured
- Serialization error (wrong protobuf version)
- Consumer lag (service overloaded)

**Solution**:
```bash
# Check Kafka topics
kafka-topics --list --bootstrap-server localhost:9092

# Check consumer groups
kafka-consumer-groups --list --bootstrap-server localhost:9092

# Check consumer lag
kafka-ui-bot → Inspect consumer group lag

# Check logs for deserialization errors
read-game-server-log → Search for "deserialize" errors
```

## Best Practices

### Field Numbering

- **1-15**: Use for frequently used fields (1 byte encoding)
- **16-2047**: Use for less frequent fields (2 bytes)
- **Never reuse deleted field numbers** (breaks old clients)

### Message Size

- **Keep messages small**: Prefer <1KB per message
- **Use pagination**: For large lists (GetInventoryRequest with page/page_size)
- **Avoid nested messages**: Flatten when possible for performance

### Enums

- **Always start with `UNSPECIFIED = 0`**: For default value
- **Use UPPER_SNAKE_CASE**: Protobuf convention
- **Add new values at the end**: Preserve existing values

```protobuf
enum ItemType {
  ITEM_TYPE_UNSPECIFIED = 0;
  EQUIPMENT = 1;
  CONSUMABLE = 2;
  MATERIAL = 3;
  // NEW_TYPE = 4;  // Add here, not in middle
}
```

### Documentation

**Document every message and field**:
```protobuf
// Represents a player's inventory item instance.
message ItemInstance {
  // Unique instance ID (database primary key).
  int64 item_instance_id = 1;

  // Item type ID (references Resource/item.yaml).
  int32 item_id = 2;

  // Quantity owned (1 for equipment, N for stackable).
  int32 quantity = 3;
}
```

## Related Documentation

- **Protocol Expert**: `.claude/agents/protocol-expert.md`
- **Battle Server**: `Source/battle/CLAUDE.md`
- **Backend Services**: `.claude/agents/backend-server-dev.md`
- **Kafka Integration**: `.claude/docs/KAFKA.md`
- **gRPC Guidelines**: `.claude/docs/GRPC.md`

---

**Last Updated**: 2025-10-27
**Maintainer**: Backend + Client Team
**Protocol Status**: Production
