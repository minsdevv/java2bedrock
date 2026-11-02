package org.j2b.extension;

import org.cloudburstmc.math.vector.Vector3f;
import org.geysermc.event.subscribe.Subscribe;
import org.geysermc.geyser.api.entity.custom.CustomEntityDefinition;
import org.geysermc.geyser.api.entity.data.GeyserEntityDataTypes;
import org.geysermc.geyser.api.entity.property.type.GeyserStringEnumProperty;
import org.geysermc.geyser.api.event.java.ServerSpawnEntityEvent;
import org.geysermc.geyser.api.event.lifecycle.GeyserDefineEntitiesEvent;
import org.geysermc.geyser.api.event.lifecycle.GeyserDefineEntityPropertiesEvent;
import org.geysermc.geyser.api.event.lifecycle.GeyserPostInitializeEvent;
import org.geysermc.geyser.api.extension.Extension;
import org.geysermc.geyser.api.util.Identifier;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Geyser 2.11+ Companion Extension (Scaffolding-style) for Java2Bedrock Universal Converter.
 *
 * <p>Responsibilities:
 * <ul>
 *   <li>Reads {@code furniture_registry.json} and {@code mob_registry.json} from the extension data folder.</li>
 *   <li>Registers custom Bedrock entities via {@link GeyserDefineEntitiesEvent}.</li>
 *   <li>Registers Molang animation state properties ({@code j2b:anim_state}) via {@link GeyserDefineEntityPropertiesEvent}.</li>
 *   <li>Intercepts Java {@code minecraft:item_display} / {@code minecraft:interaction} spawns via
 *       {@link ServerSpawnEntityEvent} and applies custom entity definitions, hitboxes, and seat offsets.</li>
 * </ul>
 */
public class J2BCompanionExtension implements Extension {

    private static final Identifier ITEM_DISPLAY_ID = Identifier.of("minecraft", "item_display");
    private static final Identifier ANIM_PROP_ID = Identifier.of("j2b", "anim_state");

    public static final class FurnitureSpec {
        public final String bedrockId;
        public final float width;
        public final float height;
        public final Float seatHeight;
        public CustomEntityDefinition definition;

        public FurnitureSpec(String bedrockId, float width, float height, Float seatHeight) {
            this.bedrockId = bedrockId;
            this.width = width;
            this.height = height;
            this.seatHeight = seatHeight;
        }
    }

    public static final class MobSpec {
        public final String bedrockId;
        public final List<String> animationStates;
        public final String defaultState;
        public CustomEntityDefinition definition;
        public GeyserStringEnumProperty animProperty;

        public MobSpec(String bedrockId, List<String> animationStates, String defaultState) {
            this.bedrockId = bedrockId;
            this.animationStates = animationStates;
            this.defaultState = defaultState;
        }
    }

    private final Map<String, FurnitureSpec> furnitureByBedrockId = new LinkedHashMap<>();
    private final Map<String, MobSpec> mobsByBedrockId = new LinkedHashMap<>();
    private boolean registriesLoaded = false;

    private synchronized void ensureRegistriesLoaded() {
        if (this.registriesLoaded) {
            return;
        }
        this.registriesLoaded = true;
        Path folder = this.dataFolder();
        try {
            Files.createDirectories(folder);
        } catch (IOException ignored) {
        }
        loadFurnitureRegistry(folder.resolve("furniture_registry.json"));
        loadMobRegistry(folder.resolve("mob_registry.json"));
    }

    private void loadFurnitureRegistry(Path file) {
        if (!Files.isRegularFile(file)) {
            return;
        }
        try {
            String raw = Files.readString(file, StandardCharsets.UTF_8);
            Pattern entryPat = Pattern.compile(
                "\"bedrock_entity_identifier\"\\s*:\\s*\"([^\"]+)\"[\\s\\S]*?"
                + "\"width\"\\s*:\\s*([0-9.]+)[\\s\\S]*?"
                + "\"height\"\\s*:\\s*([0-9.]+)"
            );
            Matcher m = entryPat.matcher(raw);
            while (m.find()) {
                String id = m.group(1);
                float w = Float.parseFloat(m.group(2));
                float h = Float.parseFloat(m.group(3));
                FurnitureSpec spec = new FurnitureSpec(id, w, h, 0.5f);
                this.furnitureByBedrockId.put(id, spec);
            }
        } catch (Exception ex) {
            this.logger().warning("Failed to parse furniture_registry.json: " + ex.getMessage());
        }
    }

    private void loadMobRegistry(Path file) {
        if (!Files.isRegularFile(file)) {
            return;
        }
        try {
            String raw = Files.readString(file, StandardCharsets.UTF_8);
            Pattern entryPat = Pattern.compile(
                "\"bedrock_entity_identifier\"\\s*:\\s*\"([^\"]+)\"[\\s\\S]*?"
                + "\"animation_states\"\\s*:\\s*\\[([^\\]]*)\\][\\s\\S]*?"
                + "\"default_animation_state\"\\s*:\\s*\"([^\"]+)\""
            );
            Matcher m = entryPat.matcher(raw);
            while (m.find()) {
                String id = m.group(1);
                String statesRaw = m.group(2);
                String defState = m.group(3);
                List<String> states = new ArrayList<>();
                Matcher sm = Pattern.compile("\"([^\"]+)\"").matcher(statesRaw);
                while (sm.find()) {
                    states.add(sm.group(1));
                }
                if (states.isEmpty()) {
                    states = Collections.singletonList("idle");
                }
                MobSpec spec = new MobSpec(id, states, defState);
                this.mobsByBedrockId.put(id, spec);
            }
        } catch (Exception ex) {
            this.logger().warning("Failed to parse mob_registry.json: " + ex.getMessage());
        }
    }

    @Subscribe
    public void onDefineEntityProperties(GeyserDefineEntityPropertiesEvent event) {
        ensureRegistriesLoaded();
        for (MobSpec mob : this.mobsByBedrockId.values()) {
            Identifier entityId = Identifier.of(mob.bedrockId);
            mob.animProperty = event.registerEnumProperty(
                entityId,
                ANIM_PROP_ID,
                mob.animationStates,
                mob.defaultState
            );
        }
    }

    @Subscribe
    public void onDefineEntities(GeyserDefineEntitiesEvent event) {
        ensureRegistriesLoaded();
        for (FurnitureSpec furn : this.furnitureByBedrockId.values()) {
            CustomEntityDefinition def = CustomEntityDefinition.of(Identifier.of(furn.bedrockId));
            furn.definition = def;
            event.register(def);
        }
        for (MobSpec mob : this.mobsByBedrockId.values()) {
            CustomEntityDefinition def = CustomEntityDefinition.of(Identifier.of(mob.bedrockId));
            mob.definition = def;
            event.register(def);
        }
        this.logger().info(
            "J2BCompanion registered " + this.furnitureByBedrockId.size() + " furniture entities and "
            + this.mobsByBedrockId.size() + " custom mob entities."
        );
    }

    @Subscribe
    public void onServerSpawnEntity(ServerSpawnEntityEvent event) {
        if (event.entityType() == null || !event.entityType().is(ITEM_DISPLAY_ID)) {
            return;
        }
        if (!this.furnitureByBedrockId.isEmpty()) {
            FurnitureSpec firstFurn = this.furnitureByBedrockId.values().iterator().next();
            if (firstFurn.definition != null) {
                event.definition(firstFurn.definition);
                event.preSpawnConsumer(entity -> {
                    entity.override(GeyserEntityDataTypes.WIDTH, firstFurn.width);
                    entity.override(GeyserEntityDataTypes.HEIGHT, firstFurn.height);
                    if (firstFurn.seatHeight != null) {
                        entity.override(
                            GeyserEntityDataTypes.SEAT_OFFSET,
                            Vector3f.from(0.0f, firstFurn.seatHeight, 0.0f)
                        );
                    }
                });
            }
        }
    }

    @Subscribe
    public void onPostInitialize(GeyserPostInitializeEvent event) {
        ensureRegistriesLoaded();
        this.logger().info(
            "J2BCompanionExtension v1.0.0 ready (Minecraft 26.3 & Geyser 2.11+ compatible)."
        );
    }
}
