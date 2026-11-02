/**
 * Campus Parking & Vehicle Tracking System (CPVTS)
 * Interactive 3D Parking Lot Visualizer (Three.js WebGL)
 *
 * Renders an interactive 3D campus parking lot with:
 * - Zone A: 10 Two-Wheeler bays (T-01 to T-10) with 3D motorcycle models when occupied.
 * - Zone B: 5 Four-Wheeler bays (F-01 to F-05) with 3D car models when occupied.
 * - Interactive orbiting, zoom, preset camera angles, raycasting, and HUD card.
 * - Real-time synchronization with the live dashboard refresh API.
 */

(function () {
    if (typeof THREE === "undefined") {
        console.warn("Three.js not loaded. 3D parking visualizer skipped.");
        return;
    }

    const Parking3D = {
        container: null,
        scene: null,
        camera: null,
        renderer: null,
        raycaster: null,
        mouse: null,
        slotsGroup: null,
        slotMeshes: {},    // Map of slot_id -> { group, baseMesh, markerMesh, vehicleMesh, data }
        selectedSlot: null,
        hoveredSlot: null,
        isDragging: false,
        previousMousePosition: { x: 0, y: 0 },
        cameraTarget: new THREE.Vector3(0, 0, 0),
        spherical: { radius: 32, theta: Math.PI / 4, phi: Math.PI / 3.4 },
        viewPreset: "isometric",
        initialized: false,
        animationFrameId: null
    };

    // Slot layout map in 3D world space
    // Zone A: Two-Wheelers (T-01 to T-10) arranged in two parallel rows along the north side
    // Zone B: Four-Wheelers (F-01 to F-05) arranged along the south side
    const SLOT_COORDINATES = {
        // Zone A: Two-Wheelers (10 slots)
        "T-01": { x: -8.0, z: -5.5, width: 1.5, depth: 3.2, zone: "two", rotation: 0 },
        "T-02": { x: -6.2, z: -5.5, width: 1.5, depth: 3.2, zone: "two", rotation: 0 },
        "T-03": { x: -4.4, z: -5.5, width: 1.5, depth: 3.2, zone: "two", rotation: 0 },
        "T-04": { x: -2.6, z: -5.5, width: 1.5, depth: 3.2, zone: "two", rotation: 0 },
        "T-05": { x: -0.8, z: -5.5, width: 1.5, depth: 3.2, zone: "two", rotation: 0 },
        "T-06": { x:  1.0, z: -5.5, width: 1.5, depth: 3.2, zone: "two", rotation: 0 },
        "T-07": { x:  2.8, z: -5.5, width: 1.5, depth: 3.2, zone: "two", rotation: 0 },
        "T-08": { x:  4.6, z: -5.5, width: 1.5, depth: 3.2, zone: "two", rotation: 0 },
        "T-09": { x:  6.4, z: -5.5, width: 1.5, depth: 3.2, zone: "two", rotation: 0 },
        "T-10": { x:  8.2, z: -5.5, width: 1.5, depth: 3.2, zone: "two", rotation: 0 },

        // Zone B: Four-Wheelers (5 slots)
        "F-01": { x: -7.2, z: 5.5, width: 3.2, depth: 5.4, zone: "four", rotation: Math.PI },
        "F-02": { x: -3.6, z: 5.5, width: 3.2, depth: 5.4, zone: "four", rotation: Math.PI },
        "F-03": { x:  0.0, z: 5.5, width: 3.2, depth: 5.4, zone: "four", rotation: Math.PI },
        "F-04": { x:  3.6, z: 5.5, width: 3.2, depth: 5.4, zone: "four", rotation: Math.PI },
        "F-05": { x:  7.2, z: 5.5, width: 3.2, depth: 5.4, zone: "four", rotation: Math.PI }
    };

    // Color definitions based on owner categories
    function getCategoryColors(category) {
        switch ((category || "").trim().toLowerCase()) {
            case "staff":
                return { body: 0x1d4ed8, trim: 0x93c5fd, emissive: 0x1e3a8a }; // Navy / Blue
            case "student":
                return { body: 0x7c3aed, trim: 0xc4b5fd, emissive: 0x5b21b6 }; // Violet / Purple
            case "visitor":
                return { body: 0xd97706, trim: 0xfde68a, emissive: 0x92400e }; // Amber / Orange
            case "vip/emergency":
            case "vip":
            case "emergency":
                return { body: 0xb45309, trim: 0xfde047, emissive: 0x78350f }; // Gold / VIP
            default:
                return { body: 0x2563eb, trim: 0x60a5fa, emissive: 0x1d4ed8 };
        }
    }

    /**
     * Creates a procedural 3D Car model (Sedan)
     */
    function create3DCar(category) {
        const carGroup = new THREE.Group();
        const colors = getCategoryColors(category);

        const paintMat = new THREE.MeshStandardMaterial({
            color: colors.body,
            roughness: 0.35,
            metalness: 0.25
        });

        const glassMat = new THREE.MeshStandardMaterial({
            color: 0x111827,
            roughness: 0.1,
            metalness: 0.8,
            transparent: true,
            opacity: 0.85
        });

        const tireMat = new THREE.MeshStandardMaterial({
            color: 0x18181b,
            roughness: 0.85
        });

        const rimMat = new THREE.MeshStandardMaterial({
            color: 0xd1d5db,
            roughness: 0.2,
            metalness: 0.8
        });

        const chromeMat = new THREE.MeshStandardMaterial({
            color: 0xe5e7eb,
            roughness: 0.2,
            metalness: 0.9
        });

        const headlightMat = new THREE.MeshBasicMaterial({ color: 0xfffbeb });
        const taillightMat = new THREE.MeshBasicMaterial({ color: 0xef4444 });

        // Lower Chassis Body
        const bodyGeo = new THREE.BoxGeometry(2.1, 0.58, 4.2);
        const bodyMesh = new THREE.Mesh(bodyGeo, paintMat);
        bodyMesh.position.y = 0.52;
        bodyMesh.castShadow = true;
        carGroup.add(bodyMesh);

        // Front Hood & Grille
        const hoodGeo = new THREE.BoxGeometry(1.95, 0.45, 1.2);
        const hoodMesh = new THREE.Mesh(hoodGeo, paintMat);
        hoodMesh.position.set(0, 0.56, 1.4);
        carGroup.add(hoodMesh);

        // Cabin / Roof Greenhouse
        const cabinGeo = new THREE.BoxGeometry(1.78, 0.56, 2.1);
        const cabinMesh = new THREE.Mesh(cabinGeo, glassMat);
        cabinMesh.position.set(0, 1.05, -0.15);
        carGroup.add(cabinMesh);

        // Roof Panel
        const roofGeo = new THREE.BoxGeometry(1.72, 0.08, 1.95);
        const roofMesh = new THREE.Mesh(roofGeo, paintMat);
        roofMesh.position.set(0, 1.34, -0.15);
        carGroup.add(roofMesh);

        // 4 Wheels with Rims
        const wheelGeo = new THREE.CylinderGeometry(0.36, 0.36, 0.24, 16);
        const rimGeo = new THREE.CylinderGeometry(0.22, 0.22, 0.26, 12);
        wheelGeo.rotateZ(Math.PI / 2);
        rimGeo.rotateZ(Math.PI / 2);

        const wheelPositions = [
            { x: -1.05, y: 0.36, z:  1.3 },
            { x:  1.05, y: 0.36, z:  1.3 },
            { x: -1.05, y: 0.36, z: -1.3 },
            { x:  1.05, y: 0.36, z: -1.3 }
        ];

        wheelPositions.forEach(pos => {
            const wheel = new THREE.Mesh(wheelGeo, tireMat);
            wheel.position.set(pos.x, pos.y, pos.z);
            wheel.castShadow = true;
            const rim = new THREE.Mesh(rimGeo, rimMat);
            wheel.add(rim);
            carGroup.add(wheel);
        });

        // Headlights (Front, z = +2.12)
        const hlGeo = new THREE.BoxGeometry(0.35, 0.16, 0.08);
        const hlLeft = new THREE.Mesh(hlGeo, headlightMat);
        hlLeft.position.set(-0.7, 0.55, 2.12);
        const hlRight = new THREE.Mesh(hlGeo, headlightMat);
        hlRight.position.set(0.7, 0.55, 2.12);
        carGroup.add(hlLeft, hlRight);

        // Taillights (Rear, z = -2.12)
        const tlGeo = new THREE.BoxGeometry(0.38, 0.15, 0.08);
        const tlLeft = new THREE.Mesh(tlGeo, taillightMat);
        tlLeft.position.set(-0.75, 0.65, -2.12);
        const tlRight = new THREE.Mesh(tlGeo, taillightMat);
        tlRight.position.set(0.75, 0.65, -2.12);
        carGroup.add(tlLeft, tlRight);

        // License Plates (Front & Back)
        const plateGeo = new THREE.BoxGeometry(0.65, 0.18, 0.04);
        const plateMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.4 });
        const plateFront = new THREE.Mesh(plateGeo, plateMat);
        plateFront.position.set(0, 0.4, 2.13);
        const plateBack = new THREE.Mesh(plateGeo, plateMat);
        plateBack.position.set(0, 0.4, -2.13);
        carGroup.add(plateFront, plateBack);

        // Soft Ground Contact Shadow
        const shadowGeo = new THREE.PlaneGeometry(2.4, 4.4);
        const shadowMat = new THREE.MeshBasicMaterial({
            color: 0x050811,
            transparent: true,
            opacity: 0.45
        });
        const shadow = new THREE.Mesh(shadowGeo, shadowMat);
        shadow.rotation.x = -Math.PI / 2;
        shadow.position.y = 0.02;
        carGroup.add(shadow);

        return carGroup;
    }

    /**
     * Creates a procedural 3D Motorcycle / Bike model
     */
    function create3DBike(category) {
        const bikeGroup = new THREE.Group();
        const colors = getCategoryColors(category);

        const paintMat = new THREE.MeshStandardMaterial({
            color: colors.body,
            roughness: 0.35,
            metalness: 0.2
        });

        const chromeMat = new THREE.MeshStandardMaterial({
            color: 0xd1d5db,
            roughness: 0.2,
            metalness: 0.85
        });

        const tireMat = new THREE.MeshStandardMaterial({
            color: 0x18181b,
            roughness: 0.9
        });

        const seatMat = new THREE.MeshStandardMaterial({
            color: 0x27272a,
            roughness: 0.7
        });

        const headlightMat = new THREE.MeshBasicMaterial({ color: 0xfef08a });
        const taillightMat = new THREE.MeshBasicMaterial({ color: 0xef4444 });

        // 2 Wheels (Front z = +0.95, Rear z = -0.95)
        const wheelGeo = new THREE.CylinderGeometry(0.38, 0.38, 0.14, 16);
        wheelGeo.rotateZ(Math.PI / 2);

        const frontWheel = new THREE.Mesh(wheelGeo, tireMat);
        frontWheel.position.set(0, 0.38, 0.95);
        frontWheel.castShadow = true;

        const rearWheel = new THREE.Mesh(wheelGeo, tireMat);
        rearWheel.position.set(0, 0.38, -0.95);
        rearWheel.castShadow = true;
        bikeGroup.add(frontWheel, rearWheel);

        // Wheel Spokes / Hubs
        const hubGeo = new THREE.CylinderGeometry(0.18, 0.18, 0.16, 12);
        hubGeo.rotateZ(Math.PI / 2);
        const frontHub = new THREE.Mesh(hubGeo, chromeMat);
        frontWheel.add(frontHub);
        const rearHub = new THREE.Mesh(hubGeo, chromeMat);
        rearWheel.add(rearHub);

        // Main Frame / Chassis
        const frameGeo = new THREE.BoxGeometry(0.24, 0.38, 1.3);
        const frameMesh = new THREE.Mesh(frameGeo, chromeMat);
        frameMesh.position.set(0, 0.55, 0);
        bikeGroup.add(frameMesh);

        // Engine Block
        const engineGeo = new THREE.BoxGeometry(0.42, 0.35, 0.45);
        const engineMesh = new THREE.Mesh(engineGeo, chromeMat);
        engineMesh.position.set(0, 0.45, -0.05);
        bikeGroup.add(engineMesh);

        // Exhaust Pipe
        const exhaustGeo = new THREE.CylinderGeometry(0.06, 0.06, 1.2, 8);
        exhaustGeo.rotateX(Math.PI / 2);
        const exhaust = new THREE.Mesh(exhaustGeo, chromeMat);
        exhaust.position.set(0.26, 0.32, -0.5);
        bikeGroup.add(exhaust);

        // Fuel Tank (Sculpted colored center)
        const tankGeo = new THREE.BoxGeometry(0.45, 0.32, 0.7);
        const tankMesh = new THREE.Mesh(tankGeo, paintMat);
        tankMesh.position.set(0, 0.82, 0.25);
        bikeGroup.add(tankMesh);

        // Seat
        const seatGeo = new THREE.BoxGeometry(0.36, 0.12, 0.65);
        const seatMesh = new THREE.Mesh(seatGeo, seatMat);
        seatMesh.position.set(0, 0.84, -0.35);
        bikeGroup.add(seatMesh);

        // Front Fork Steering Columns
        const forkGeo = new THREE.CylinderGeometry(0.05, 0.05, 0.85, 8);
        forkGeo.rotateX(-0.35);
        const forkLeft = new THREE.Mesh(forkGeo, chromeMat);
        forkLeft.position.set(-0.16, 0.68, 0.75);
        const forkRight = new THREE.Mesh(forkGeo, chromeMat);
        forkRight.position.set(0.16, 0.68, 0.75);
        bikeGroup.add(forkLeft, forkRight);

        // Handlebars
        const barGeo = new THREE.CylinderGeometry(0.04, 0.04, 0.75, 8);
        barGeo.rotateZ(Math.PI / 2);
        const barMesh = new THREE.Mesh(barGeo, chromeMat);
        barMesh.position.set(0, 1.05, 0.65);
        bikeGroup.add(barMesh);

        // Headlight (Front z = +1.0)
        const hlGeo = new THREE.CylinderGeometry(0.12, 0.12, 0.1, 12);
        hlGeo.rotateX(Math.PI / 2);
        const hlMesh = new THREE.Mesh(hlGeo, headlightMat);
        hlMesh.position.set(0, 0.95, 0.98);
        bikeGroup.add(hlMesh);

        // Taillight (Rear z = -0.98)
        const tlGeo = new THREE.BoxGeometry(0.14, 0.08, 0.06);
        const tlMesh = new THREE.Mesh(tlGeo, taillightMat);
        tlMesh.position.set(0, 0.75, -0.98);
        bikeGroup.add(tlMesh);

        // Soft Ground Contact Shadow
        const shadowGeo = new THREE.PlaneGeometry(1.2, 2.6);
        const shadowMat = new THREE.MeshBasicMaterial({
            color: 0x050811,
            transparent: true,
            opacity: 0.4
        });
        const shadow = new THREE.Mesh(shadowGeo, shadowMat);
        shadow.rotation.x = -Math.PI / 2;
        shadow.position.y = 0.02;
        bikeGroup.add(shadow);

        return bikeGroup;
    }

    /**
     * Initializes the Three.js 3D Scene
     */
    Parking3D.init = function (containerId) {
        const container = document.getElementById(containerId || "parking3dContainer");
        if (!container) return;
        Parking3D.container = container;

        // Clean container contents (except HUD and Legend)
        const existingCanvas = container.querySelector("canvas");
        if (existingCanvas) {
            existingCanvas.remove();
        }

        const width = container.clientWidth || 800;
        const height = container.clientHeight || 420;

        // Scene
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x0f172a); // Deep modern slate background
        Parking3D.scene = scene;

        // Camera
        const aspect = width / height;
        const camera = new THREE.PerspectiveCamera(40, aspect, 0.1, 1000);
        Parking3D.camera = camera;
        Parking3D.updateCameraPosition();

        // WebGL Renderer with High-DPI support
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
        renderer.setSize(width, height);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        container.appendChild(renderer.domElement);
        Parking3D.renderer = renderer;

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
        scene.add(ambientLight);

        const sunLight = new THREE.DirectionalLight(0xfffbeb, 0.85);
        sunLight.position.set(15, 25, 18);
        sunLight.castShadow = true;
        sunLight.shadow.mapSize.width = 1024;
        sunLight.shadow.mapSize.height = 1024;
        sunLight.shadow.camera.near = 5;
        sunLight.shadow.camera.far = 60;
        sunLight.shadow.camera.left = -20;
        sunLight.shadow.camera.right = 20;
        sunLight.shadow.camera.top = 20;
        sunLight.shadow.camera.bottom = -20;
        scene.add(sunLight);

        const hemiLight = new THREE.HemisphereLight(0x93c5fd, 0x1e293b, 0.4);
        scene.add(hemiLight);

        // Ground & Parking Lot Geometry
        Parking3D.buildEnvironment();

        // Slots Group
        const slotsGroup = new THREE.Group();
        scene.add(slotsGroup);
        Parking3D.slotsGroup = slotsGroup;

        // Build individual 3D bay foundations
        Parking3D.buildSlotBays();

        // Raycasting & Interaction Setup
        Parking3D.raycaster = new THREE.Raycaster();
        Parking3D.mouse = new THREE.Vector2();

        Parking3D.setupEventListeners();

        // Start render loop
        Parking3D.animate();

        Parking3D.initialized = true;

        // ResizeObserver for fully responsive fluid resizing
        if (window.ResizeObserver) {
            const ro = new ResizeObserver(entries => {
                for (let entry of entries) {
                    Parking3D.onWindowResize();
                }
            });
            ro.observe(container);
        }

        // Fetch initial data if available in window or via API
        if (window.CPVTS && window.CPVTS.lastDashboardData) {
            Parking3D.update(window.CPVTS.lastDashboardData);
        } else {
            fetch("/api/dashboard")
                .then(r => r.json())
                .then(data => Parking3D.update(data))
                .catch(() => {});
        }
    };

    /**
     * Builds asphalt ground, curbs, road divider lines, and zone barriers
     */
    Parking3D.buildEnvironment = function () {
        const scene = Parking3D.scene;

        // Main Asphalt Lot Ground
        const groundGeo = new THREE.PlaneGeometry(36, 26);
        const groundMat = new THREE.MeshStandardMaterial({
            color: 0x1e293b, // Slate asphalt
            roughness: 0.85,
            metalness: 0.1
        });
        const ground = new THREE.Mesh(groundGeo, groundMat);
        ground.rotation.x = -Math.PI / 2;
        ground.receiveShadow = true;
        scene.add(ground);

        // Perimeter Curb Border
        const curbMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.7 });
        const curbThickness = 0.4;
        const curbHeight = 0.25;

        const northCurb = new THREE.Mesh(new THREE.BoxGeometry(36, curbHeight, curbThickness), curbMat);
        northCurb.position.set(0, curbHeight / 2, -13);
        const southCurb = new THREE.Mesh(new THREE.BoxGeometry(36, curbHeight, curbThickness), curbMat);
        southCurb.position.set(0, curbHeight / 2, 13);
        const westCurb = new THREE.Mesh(new THREE.BoxGeometry(curbThickness, curbHeight, 26), curbMat);
        westCurb.position.set(-18, curbHeight / 2, 0);
        const eastCurb = new THREE.Mesh(new THREE.BoxGeometry(curbThickness, curbHeight, 26), curbMat);
        eastCurb.position.set(18, curbHeight / 2, 0);

        scene.add(northCurb, southCurb, westCurb, eastCurb);

        // Central Driving Lane Divider (Z = 0)
        const lineMat = new THREE.MeshBasicMaterial({ color: 0xfbbf24 }); // Amber road stripes
        for (let x = -14; x <= 14; x += 3.5) {
            const dash = new THREE.Mesh(new THREE.PlaneGeometry(2.0, 0.2), lineMat);
            dash.rotation.x = -Math.PI / 2;
            dash.position.set(x, 0.015, 0);
            scene.add(dash);
        }

        // Zone Demarcation Road Letters / Labels (Visual Markers)
        const zoneDividerMat = new THREE.MeshBasicMaterial({ color: 0x64748b, transparent: true, opacity: 0.6 });
        const northZoneLine = new THREE.Mesh(new THREE.PlaneGeometry(32, 0.1), zoneDividerMat);
        northZoneLine.rotation.x = -Math.PI / 2;
        northZoneLine.position.set(0, 0.015, -2.2);
        const southZoneLine = new THREE.Mesh(new THREE.PlaneGeometry(32, 0.1), zoneDividerMat);
        southZoneLine.rotation.x = -Math.PI / 2;
        southZoneLine.position.set(0, 0.015, 2.2);
        scene.add(northZoneLine, southZoneLine);
    };

    /**
     * Builds individual slot bay meshes with ground markings, slot text, and status glow
     */
    Parking3D.buildSlotBays = function () {
        const group = Parking3D.slotsGroup;
        const bays = SLOT_COORDINATES;

        for (const [slotId, cfg] of Object.entries(bays)) {
            const bayGroup = new THREE.Group();
            bayGroup.position.set(cfg.x, 0, cfg.z);
            bayGroup.userData = { slotId: slotId, config: cfg };

            // Bay Base Plate (slightly raised for interactive raycasting)
            const baseGeo = new THREE.BoxGeometry(cfg.width, 0.1, cfg.depth);
            const baseMat = new THREE.MeshStandardMaterial({
                color: 0x141e30,
                roughness: 0.7,
                metalness: 0.1
            });
            const baseMesh = new THREE.Mesh(baseGeo, baseMat);
            baseMesh.position.y = 0.05;
            baseMesh.receiveShadow = true;
            baseMesh.userData = { slotId: slotId };
            bayGroup.add(baseMesh);

            // Painted Boundary Lines (U-shaped parking bay lines)
            const lineMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
            const lineWidth = 0.1;
            const halfW = cfg.width / 2;
            const halfD = cfg.depth / 2;

            // Left line
            const leftLine = new THREE.Mesh(new THREE.BoxGeometry(lineWidth, 0.04, cfg.depth), lineMat);
            leftLine.position.set(-halfW, 0.1, 0);
            // Right line
            const rightLine = new THREE.Mesh(new THREE.BoxGeometry(lineWidth, 0.04, cfg.depth), lineMat);
            rightLine.position.set(halfW, 0.1, 0);
            // Back stopper line
            const backZ = cfg.zone === "two" ? -halfD : halfD;
            const backLine = new THREE.Mesh(new THREE.BoxGeometry(cfg.width, 0.04, lineWidth), lineMat);
            backLine.position.set(0, 0.1, backZ);

            bayGroup.add(leftLine, rightLine, backLine);

            // Wheel Stopper Curb (for Four-Wheelers in Zone B)
            if (cfg.zone === "four") {
                const stopCurb = new THREE.Mesh(
                    new THREE.BoxGeometry(cfg.width * 0.75, 0.18, 0.25),
                    new THREE.MeshStandardMaterial({ color: 0xf59e0b, roughness: 0.6 })
                );
                stopCurb.position.set(0, 0.09, halfD - 0.5);
                bayGroup.add(stopCurb);
            }

            // Interactive Status Ground Indicator (Glowing Green when Vacant, Red/Amber when Occupied)
            const indicatorGeo = new THREE.PlaneGeometry(cfg.width * 0.8, cfg.depth * 0.85);
            const indicatorMat = new THREE.MeshBasicMaterial({
                color: 0x10b981, // Emerald vacant glow
                transparent: true,
                opacity: 0.18
            });
            const indicatorMesh = new THREE.Mesh(indicatorGeo, indicatorMat);
            indicatorMesh.rotation.x = -Math.PI / 2;
            indicatorMesh.position.y = 0.11;
            bayGroup.add(indicatorMesh);

            group.add(bayGroup);

            // Store reference for quick lookups
            Parking3D.slotMeshes[slotId] = {
                group: bayGroup,
                baseMesh: baseMesh,
                indicatorMesh: indicatorMesh,
                vehicleMesh: null,
                data: null,
                config: cfg
            };
        }
    };

    /**
     * Updates 3D parking slots with live backend data from /api/dashboard
     */
    Parking3D.update = function (dashboardData) {
        if (!dashboardData || !dashboardData.slots) return;

        dashboardData.slots.forEach(slotData => {
            const slotId = slotData.slot_id;
            const slotObj = Parking3D.slotMeshes[slotId];
            if (!slotObj) return;

            slotObj.data = slotData;
            const isOccupied = slotData.status === "Occupied";
            const isReserved = slotData.status === "Reserved";

            // Update Ground Indicator Glow
            if (isOccupied) {
                slotObj.indicatorMesh.material.color.setHex(0xef4444); // Red glow
                slotObj.indicatorMesh.material.opacity = 0.28;
            } else if (isReserved) {
                slotObj.indicatorMesh.material.color.setHex(0xf59e0b); // Amber VIP glow
                slotObj.indicatorMesh.material.opacity = 0.35;
            } else {
                slotObj.indicatorMesh.material.color.setHex(0x10b981); // Emerald vacant glow
                slotObj.indicatorMesh.material.opacity = 0.18;
            }

            // Update 3D Vehicle in Bay
            if (isOccupied) {
                // If vehicle mesh not already present, spawn it
                if (!slotObj.vehicleMesh) {
                    let vehicle = null;
                    if (slotData.vehicle_type === "Two-Wheeler") {
                        vehicle = create3DBike(slotData.owner_category);
                    } else {
                        vehicle = create3DCar(slotData.owner_category);
                    }

                    // Apply rotation from slot config
                    vehicle.rotation.y = slotObj.config.rotation || 0;
                    vehicle.position.y = 0.05;

                    // Smooth entrance scale animation
                    vehicle.scale.set(0.01, 0.01, 0.01);
                    slotObj.group.add(vehicle);
                    slotObj.vehicleMesh = vehicle;

                    // Animate spawn smoothly
                    let s = 0.01;
                    const spawnInterval = setInterval(() => {
                        s += 0.18;
                        if (s >= 1) {
                            vehicle.scale.set(1, 1, 1);
                            clearInterval(spawnInterval);
                        } else {
                            vehicle.scale.set(s, s, s);
                        }
                    }, 16);
                }
            } else {
                // Despawn vehicle if slot became vacant
                if (slotObj.vehicleMesh) {
                    slotObj.group.remove(slotObj.vehicleMesh);
                    slotObj.vehicleMesh = null;
                }
            }
        });

        // Update 3D HUD if a slot was currently selected
        if (Parking3D.selectedSlot) {
            Parking3D.showSlotHUD(Parking3D.selectedSlot);
        }
    };

    /**
     * Camera View Presets
     */
    Parking3D.updateCameraPosition = function () {
        const cam = Parking3D.camera;
        if (!cam) return;

        const s = Parking3D.spherical;
        cam.position.x = s.radius * Math.sin(s.phi) * Math.sin(s.theta);
        cam.position.y = s.radius * Math.cos(s.phi);
        cam.position.z = s.radius * Math.sin(s.phi) * Math.cos(s.theta);
        cam.lookAt(Parking3D.cameraTarget);
    };

    Parking3D.setView = function (viewName) {
        Parking3D.viewPreset = viewName;
        switch (viewName) {
            case "isometric":
                Parking3D.spherical = { radius: 34, theta: Math.PI / 4, phi: Math.PI / 3.4 };
                Parking3D.cameraTarget.set(0, 0, 0);
                break;
            case "topdown":
                Parking3D.spherical = { radius: 32, theta: 0.001, phi: 0.08 };
                Parking3D.cameraTarget.set(0, 0, 0);
                break;
            case "perspective":
                Parking3D.spherical = { radius: 28, theta: 0, phi: Math.PI / 2.5 };
                Parking3D.cameraTarget.set(0, 1.0, 0);
                break;
        }
        Parking3D.updateCameraPosition();
    };

    /**
     * Mouse & Touch Orbit Controls
     */
    Parking3D.setupEventListeners = function () {
        const dom = Parking3D.renderer.domElement;

        dom.addEventListener("mousedown", e => {
            Parking3D.isDragging = true;
            Parking3D.previousMousePosition = { x: e.clientX, y: e.clientY };
        });

        window.addEventListener("mouseup", () => {
            Parking3D.isDragging = false;
        });

        dom.addEventListener("mousemove", e => {
            const rect = dom.getBoundingClientRect();
            Parking3D.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
            Parking3D.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

            if (Parking3D.isDragging) {
                const deltaX = e.clientX - Parking3D.previousMousePosition.x;
                const deltaY = e.clientY - Parking3D.previousMousePosition.y;

                Parking3D.spherical.theta -= deltaX * 0.007;
                Parking3D.spherical.phi = Math.max(0.08, Math.min(Math.PI / 2.1, Parking3D.spherical.phi - deltaY * 0.007));
                Parking3D.updateCameraPosition();

                Parking3D.previousMousePosition = { x: e.clientX, y: e.clientY };
            } else {
                Parking3D.handleHover();
            }
        });

        // Wheel Zoom
        dom.addEventListener("wheel", e => {
            e.preventDefault();
            Parking3D.spherical.radius = Math.max(14, Math.min(55, Parking3D.spherical.radius + e.deltaY * 0.04));
            Parking3D.updateCameraPosition();
        }, { passive: false });

        // Touch Interaction (Mobile)
        let touchStartDist = 0;
        dom.addEventListener("touchstart", e => {
            if (e.touches.length === 1) {
                Parking3D.isDragging = true;
                Parking3D.previousMousePosition = { x: e.touches[0].clientX, y: e.touches[0].clientY };
            } else if (e.touches.length === 2) {
                touchStartDist = Math.hypot(
                    e.touches[0].clientX - e.touches[1].clientX,
                    e.touches[0].clientY - e.touches[1].clientY
                );
            }
        });

        dom.addEventListener("touchmove", e => {
            if (e.touches.length === 1 && Parking3D.isDragging) {
                const deltaX = e.touches[0].clientX - Parking3D.previousMousePosition.x;
                const deltaY = e.touches[0].clientY - Parking3D.previousMousePosition.y;

                Parking3D.spherical.theta -= deltaX * 0.008;
                Parking3D.spherical.phi = Math.max(0.1, Math.min(Math.PI / 2.1, Parking3D.spherical.phi - deltaY * 0.008));
                Parking3D.updateCameraPosition();

                Parking3D.previousMousePosition = { x: e.touches[0].clientX, y: e.touches[0].clientY };
            } else if (e.touches.length === 2) {
                const dist = Math.hypot(
                    e.touches[0].clientX - e.touches[1].clientX,
                    e.touches[0].clientY - e.touches[1].clientY
                );
                const deltaDist = touchStartDist - dist;
                Parking3D.spherical.radius = Math.max(14, Math.min(55, Parking3D.spherical.radius + deltaDist * 0.05));
                Parking3D.updateCameraPosition();
                touchStartDist = dist;
            }
        });

        dom.addEventListener("touchend", () => {
            Parking3D.isDragging = false;
        });

        // Click on Bay to focus & inspect
        dom.addEventListener("click", e => {
            const rect = dom.getBoundingClientRect();
            Parking3D.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
            Parking3D.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

            Parking3D.raycaster.setFromCamera(Parking3D.mouse, Parking3D.camera);
            const clickableMeshes = Object.values(Parking3D.slotMeshes).map(s => s.baseMesh);
            const intersects = Parking3D.raycaster.intersectObjects(clickableMeshes);

            if (intersects.length > 0) {
                const slotId = intersects[0].object.userData.slotId;
                Parking3D.selectSlot(slotId);
            }
        });

        // View Controls Preset Buttons
        const viewBtns = document.querySelectorAll(".view-btn[data-view]");
        viewBtns.forEach(btn => {
            btn.addEventListener("click", function () {
                viewBtns.forEach(b => b.classList.remove("active"));
                this.classList.add("active");
                Parking3D.setView(this.dataset.view);
            });
        });

        const resetBtn = document.getElementById("resetCameraBtn");
        if (resetBtn) {
            resetBtn.addEventListener("click", () => {
                viewBtns.forEach(b => b.classList.toggle("active", b.dataset.view === "isometric"));
                Parking3D.setView("isometric");
            });
        }
    };

    /**
     * Raycasting Hover Detection
     */
    Parking3D.handleHover = function () {
        Parking3D.raycaster.setFromCamera(Parking3D.mouse, Parking3D.camera);
        const clickableMeshes = Object.values(Parking3D.slotMeshes).map(s => s.baseMesh);
        const intersects = Parking3D.raycaster.intersectObjects(clickableMeshes);

        if (intersects.length > 0) {
            const slotId = intersects[0].object.userData.slotId;
            if (Parking3D.hoveredSlot !== slotId) {
                Parking3D.hoveredSlot = slotId;
                Parking3D.renderer.domElement.style.cursor = "pointer";
            }
        } else {
            if (Parking3D.hoveredSlot) {
                Parking3D.hoveredSlot = null;
                Parking3D.renderer.domElement.style.cursor = "default";
            }
        }
    };

    /**
     * Selects and shows HUD for a specific bay
     */
    Parking3D.selectSlot = function (slotId) {
        Parking3D.selectedSlot = slotId;
        Parking3D.showSlotHUD(slotId);
    };

    /**
     * Shows HUD overlay card
     */
    Parking3D.showSlotHUD = function (slotId) {
        const hud = document.getElementById("parking3dHud");
        if (!hud) return;

        const slotObj = Parking3D.slotMeshes[slotId];
        if (!slotObj || !slotObj.data) {
            hud.style.display = "none";
            return;
        }

        const d = slotObj.data;
        const isOccupied = d.status === "Occupied";
        const isReserved = d.status === "Reserved";
        const catClass = (d.owner_category || "").toLowerCase();
        const cardClass = isOccupied ? 'occupied' : (isReserved ? 'reserved' : 'available');
        const badgeClass = isOccupied ? 'occupied' : (isReserved ? 'reserved' : 'available');

        hud.innerHTML = `
            <div class="hud-card ${cardClass}">
                <div class="hud-header">
                    <strong class="hud-slot-id">${d.slot_id}</strong>
                    <span class="hud-status-badge ${badgeClass}">${isOccupied && isReserved ? 'OCCUPIED (VIP)' : (isReserved ? 'RESERVED' : d.status.toUpperCase())}</span>
                    <button type="button" class="hud-close-btn" onclick="document.getElementById('parking3dHud').style.display='none'">×</button>
                </div>
                <div class="hud-body">
                    ${isOccupied ? `
                        <div class="hud-vehicle-num">${d.vehicle_number}</div>
                        <div class="hud-meta-row">
                            <span>Type: <strong>${d.vehicle_type}</strong></span>
                            <span>Category: <span class="cat-chip ${catClass}">${d.owner_category}</span>${isReserved ? ' <span class="cat-chip reserved">VIP Bay</span>' : ''}</span>
                        </div>
                        <div class="hud-meta-row">
                            <span>Entry: <strong>${d.entry_time_display || '--'}</strong></span>
                            <span>Zone: <strong>${d.zone || '--'}</strong></span>
                        </div>
                        <div class="hud-actions">
                            <a href="/exit" class="btn primary btn-sm">Process Check-Out</a>
                        </div>
                    ` : isReserved ? `
                        <p class="hud-vacant-text" style="color: var(--amber-text); font-weight: 600;">Dedicated bay reserved for VIP / Emergency vehicles.</p>
                        <div class="hud-meta-row">
                            <span>Dedicated Type: <strong>${d.vehicle_type}</strong></span>
                            <span>Zone: <strong>${d.zone || '--'}</strong></span>
                        </div>
                        <div class="hud-actions" style="display: flex; gap: 6px;">
                            <a href="/entry?category=VIP/Emergency&slot_id=${d.slot_id}" class="btn primary btn-sm">Park VIP Vehicle</a>
                            <a href="/reserve?slot_id=${d.slot_id}" class="btn secondary btn-sm">Manage Bay</a>
                        </div>
                    ` : `
                        <p class="hud-vacant-text">Bay is clean and ready for assignment.</p>
                        <div class="hud-meta-row">
                            <span>Dedicated Type: <strong>${d.vehicle_type}</strong></span>
                            <span>Zone: <strong>${d.zone || '--'}</strong></span>
                        </div>
                        <div class="hud-actions">
                            <a href="/entry" class="btn primary btn-sm">Check-In Vehicle Here</a>
                        </div>
                    `}
                </div>
            </div>
        `;
        hud.style.display = "block";
    };

    /**
     * Responsive Window Resize
     */
    Parking3D.onWindowResize = function () {
        if (!Parking3D.container || !Parking3D.renderer || !Parking3D.camera) return;
        const width = Parking3D.container.clientWidth;
        const height = Parking3D.container.clientHeight || 420;

        Parking3D.camera.aspect = width / height;
        Parking3D.camera.updateProjectionMatrix();
        Parking3D.renderer.setSize(width, height);
    };

    /**
     * Main Animation & Render Loop
     */
    Parking3D.animate = function () {
        Parking3D.animationFrameId = requestAnimationFrame(Parking3D.animate);

        // Gentle idle hover animation for occupied vehicles
        const time = Date.now() * 0.0015;
        Object.values(Parking3D.slotMeshes).forEach(slot => {
            if (slot.vehicleMesh) {
                // Micro bobbing for lively visual presence
                slot.vehicleMesh.position.y = 0.05 + Math.sin(time + slot.config.x) * 0.015;
            }
        });

        Parking3D.renderer.render(Parking3D.scene, Parking3D.camera);
    };

    // Expose global controller
    window.Parking3D = Parking3D;
})();

