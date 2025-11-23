from degtrig import degSin, degCos
from direct.showbase.ShowBase import ShowBase
from panda3d.core import *
from direct.gui.OnscreenImage import OnscreenImage
import random
import time
from noise3d import PerlinNoise3D
from keymap import keyMap

class VoxelEngine(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)

        self.selectedBlockType = 'grass'
        self.gravity = -25.0
        self.jumpStrength = 10.0
        self.playerVelocityZ = 0.0
        self.grounded = False
        self.spawnPos = (0, 0, 50)

        self.chunk_size = 8
        self.block_scale = 2
        self.view_distance = 3
        self.max_height = 12
        self.cave_threshold = 0.55
        self.height_octaves = 4
        self.cave_octaves = 3

        self.world_seed = random.randint(5000, 9000)
        self.noise = PerlinNoise3D(seed=self.world_seed)

        self.chunks = {}

        self.loadModels()
        self.setupLights()
        self.setupPlayerPhysics()
        self.setupCamera()
        self.setupSkybox()
        self.captureMouse()
        self.setupControls()

        taskMgr.add(self.update, 'update')

    def setupControls(self):
        self.keyMap = keyMap

        self.accept('escape', self.releaseMouse)
        self.accept('mouse1', self.placeBlock)
        self.accept('mouse3', self.handleRightClick)

        self.accept('w', self.updateKeyMap, ['forward', True])
        self.accept('w-up', self.updateKeyMap, ['forward', False])
        self.accept('a', self.updateKeyMap, ['left', True])
        self.accept('a-up', self.updateKeyMap, ['left', False])
        self.accept('s', self.updateKeyMap, ['backward', True])
        self.accept('s-up', self.updateKeyMap, ['backward', False])
        self.accept('d', self.updateKeyMap, ['right', True])
        self.accept('d-up', self.updateKeyMap, ['right', False])
        self.accept('space', self.updateKeyMap, ['up', True])
        self.accept('space-up', self.updateKeyMap, ['up', False])

        self.accept('1', self.setSelectedBlockType, ['grass'])
        self.accept('2', self.setSelectedBlockType, ['dirt'])
        self.accept('3', self.setSelectedBlockType, ['sand'])
        self.accept('4', self.setSelectedBlockType, ['stone'])

    def update(self, task):
        dt = globalClock.getDt()
        playerMoveSpeed = 10
        x_movement = 0.0
        y_movement = 0.0

        if self.keyMap['forward']:
            x_movement -= dt * playerMoveSpeed * degSin(camera.getH())
            y_movement += dt * playerMoveSpeed * degCos(camera.getH())
        if self.keyMap['backward']:
            x_movement += dt * playerMoveSpeed * degSin(camera.getH())
            y_movement -= dt * playerMoveSpeed * degCos(camera.getH())
        if self.keyMap['left']:
            x_movement -= dt * playerMoveSpeed * degCos(camera.getH())
            y_movement -= dt * playerMoveSpeed * degSin(camera.getH())
        if self.keyMap['right']:
            x_movement += dt * playerMoveSpeed * degCos(camera.getH())
            y_movement += dt * playerMoveSpeed * degSin(camera.getH())

        self.groundRayNodePath.setPos(self.camera.getPos())
        self.groundRayNodePath.setHpr(0, 0, 0)

        self.cTrav.traverse(render)
        entries = [self.groundHandler.getEntry(i) for i in range(self.groundHandler.getNumEntries())]
        entries.sort(key=lambda e: e.getSurfacePoint(render).getZ())

        groundZ = None
        if entries:
            groundZ = entries[-1].getSurfacePoint(render).getZ() + 2.0

        self.playerVelocityZ += self.gravity * dt
        newZ = camera.getZ() + self.playerVelocityZ * dt

        if groundZ is not None:
            heightDiff = newZ - groundZ
            if heightDiff <= 0:
                newZ = groundZ
                self.playerVelocityZ = 0
                self.grounded = True
            else:
                self.grounded = False
        else:
            self.grounded = False

        if self.keyMap['up'] and self.grounded:
            self.playerVelocityZ = self.jumpStrength
            self.grounded = False

        cam_x = camera.getX()
        cam_y = camera.getY()
        cam_z = camera.getZ()

        desired_dx = x_movement
        desired_dy = y_movement

        self.playerCollider.setPos(cam_x, cam_y, cam_z)

        final_dx = desired_dx
        final_dy = desired_dy

        if abs(desired_dx) > 1e-6:
            test_x = cam_x + desired_dx
            test_y = cam_y + final_dy
            self.playerCollider.setPos(test_x, test_y, cam_z)
            self.cTrav.traverse(render)
            num_side = self.sideHandler.getNumEntries()
            if num_side > 0:
                final_dx = 0.0

        if abs(desired_dy) > 1e-6:
            test_x = cam_x + final_dx
            test_y = cam_y + desired_dy
            self.playerCollider.setPos(test_x, test_y, cam_z)
            self.cTrav.traverse(render)
            num_side = self.sideHandler.getNumEntries()
            if num_side > 0:
                final_dy = 0.0

        self.playerCollider.setPos(cam_x + final_dx, cam_y + final_dy, cam_z)

        camera.setPos(
            cam_x + final_dx,
            cam_y + final_dy,
            newZ
        )

        if camera.getZ() < -200:
            self.respawnPlayer()

        if self.cameraSwingActivated:
            md = self.win.getPointer(0)
            mouseX = md.getX()
            mouseY = md.getY()

            mouseChangeX = mouseX - self.lastMouseX
            mouseChangeY = mouseY - self.lastMouseY

            self.cameraSwingFactor = 10
            currentH = self.camera.getH()
            currentP = self.camera.getP()

            self.camera.setHpr(
                currentH - mouseChangeX * dt * self.cameraSwingFactor,
                min(90, max(-90, currentP - mouseChangeY * dt * self.cameraSwingFactor)),
                0
            )

            self.lastMouseX = mouseX
            self.lastMouseY = mouseY

        self.ensureChunksAroundPlayer()
        return task.cont

    def world_to_block(self, wx, wy, wz):
        bx = int(round(wx / self.block_scale))
        by = int(round(wy / self.block_scale))
        bz = int(round(wz / self.block_scale))
        return bx, by, bz

    def block_to_world(self, bx, by, bz):
        return bx * self.block_scale, by * self.block_scale, bz * self.block_scale

    def block_to_chunk(self, bx, by):
        cx = bx // self.chunk_size if bx >= 0 else -((-bx - 1) // self.chunk_size) - 1
        cy = by // self.chunk_size if by >= 0 else -((-by - 1) // self.chunk_size) - 1
        return cx, cy

    def ensureChunksAroundPlayer(self):
        px, py, pz = camera.getPos()
        pbx, pby, pbz = self.world_to_block(px, py, pz)
        pcx, pcy = self.block_to_chunk(pbx, pby)

        to_have = set()
        for dx in range(-self.view_distance, self.view_distance + 1):
            for dy in range(-self.view_distance, self.view_distance + 1):
                dist = max(abs(dx), abs(dy))
                if dist <= self.view_distance:
                    to_have.add((pcx + dx, pcy + dy))

        for key in to_have:
            if key not in self.chunks:
                self.generateChunk(key[0], key[1])

        existing = list(self.chunks.keys())
        for key in existing:
            if key not in to_have:
                self.unloadChunk(key[0], key[1])

    def generateChunk(self, cx, cy):
        chunk_node = render.attachNewNode(f'chunk-{cx}-{cy}')
        chunk_blocks = {}

        base_bx = cx * self.chunk_size
        base_by = cy * self.chunk_size

        for lx in range(self.chunk_size):
            for ly in range(self.chunk_size):
                bx = base_bx + lx
                by = base_by + ly

                height_noise = self.noise.fractal_noise(bx * 0.05, by * 0.05, 0.0, octaves=self.height_octaves)
                column_height = int(height_noise * self.max_height)

                if column_height < 2:
                    column_height = 2

                for bz in range(column_height):
                    if bz > 1:
                        cave_val = self.noise.fractal_noise(
                            bx * 0.08, by * 0.08, bz * 0.08, octaves=self.cave_octaves
                        )
                        solid = (cave_val > self.cave_threshold)
                        if not solid:
                            continue

                    block_type = 'stone'
                    if bz > column_height - 5:
                        block_type = 'sand'
                    if bz > column_height - 3:
                        block_type = 'dirt'
                    if bz == column_height - 1:
                        block_type = 'grass'

                    world_x, world_y, world_z = self.block_to_world(bx, by, bz)
                    node = self.createNewBlock(
                        world_x, world_y, world_z, block_type,
                        parent=chunk_node, track_in_chunk=True
                    )
                    chunk_blocks[(bx, by, bz)] = node

        self.chunks[(cx, cy)] = {
            'node': chunk_node,
            'blocks': chunk_blocks,
            'created_at': time.time()
        }

    def unloadChunk(self, cx, cy):
        info = self.chunks.get((cx, cy))
        if not info:
            return
        chunk_node = info['node']
        chunk_node.removeNode()
        del self.chunks[(cx, cy)]

    def createNewBlock(self, x, y, z, type, parent=None, track_in_chunk=False):
        if parent is None:
            parent = render

        newBlockNode = parent.attachNewNode('new-block-placeholder')
        newBlockNode.setPos(x, y, z)

        if type == 'grass':
            self.grassBlock.instanceTo(newBlockNode)
        elif type == 'dirt':
            self.dirtBlock.instanceTo(newBlockNode)
        elif type == 'sand':
            self.sandBlock.instanceTo(newBlockNode)
        else:
            self.stoneBlock.instanceTo(newBlockNode)

        half = self.block_scale / 2
        blockSolid = CollisionBox((-half, -half, -half), (half, half, half))
        blockNode = CollisionNode('block-collision-node')
        blockNode.addSolid(blockSolid)
        blockNode.setIntoCollideMask(BitMask32.bit(1))
        collider = newBlockNode.attachNewNode(blockNode)
        collider.setPythonTag('owner', newBlockNode)

        return newBlockNode

    def loadModels(self):
        self.grassBlock = loader.loadModel('3DBlockModels/grass-block.glb')
        self.dirtBlock = loader.loadModel('3DBlockModels/dirt-block.glb')
        self.stoneBlock = loader.loadModel('3DBlockModels/stone-block.glb')
        self.sandBlock = loader.loadModel('3DBlockModels/sand-block.glb')

    def setupLights(self):
        mainLight = DirectionalLight('main.py light')
        mainLightNodePath = render.attachNewNode(mainLight)
        mainLightNodePath.setHpr(30, -60, 0)
        render.setLight(mainLightNodePath)

        ambientLight = AmbientLight('ambient light')
        ambientLight.setColor((0.3, 0.3, 0.3, 1))
        ambientLightNodePath = render.attachNewNode(ambientLight)
        render.setLight(ambientLightNodePath)

    def setupPlayerPhysics(self):
        self.groundRay = CollisionRay()
        self.groundRay.setOrigin(0, 0, 0)
        self.groundRay.setDirection(0, 0, -1)

        rayNode = CollisionNode('playerRay')
        rayNode.addSolid(self.groundRay)
        rayNode.setFromCollideMask(BitMask32.bit(1))
        self.groundRayNodePath = render.attachNewNode(rayNode)
        self.groundRayNodePath.setPos(self.camera.getPos())
        self.groundHandler = CollisionHandlerQueue()

        playerSolid = CollisionBox((-0.4, -0.4, -0.9), (0.4, 0.4, 0.9))
        playerNode = CollisionNode('playerCollider')
        playerNode.addSolid(playerSolid)
        playerNode.setFromCollideMask(BitMask32.bit(1))
        playerNode.setIntoCollideMask(BitMask32.allOff())

        self.playerCollider = render.attachNewNode(playerNode)
        self.playerCollider.setPos(self.camera.getPos())
        self.sideHandler = CollisionHandlerQueue()

        self.cTrav = CollisionTraverser()
        self.cTrav.addCollider(self.groundRayNodePath, self.groundHandler)
        self.cTrav.addCollider(self.playerCollider, self.sideHandler)

    def setSelectedBlockType(self, type):
        self.selectedBlockType = type

    def handleRightClick(self):
        self.captureMouse()
        self.removeBlock()

    def removeBlock(self):
        if self.rayQueue.getNumEntries() > 0:
            self.rayQueue.sortEntries()
            rayHit = self.rayQueue.getEntry(0)

            hitNodePath = rayHit.getIntoNodePath()
            hitObject = hitNodePath.getPythonTag('owner')
            if not hitObject:
                return
            distanceFromPlayer = hitObject.getDistance(self.camera)

            if distanceFromPlayer < 200:
                hitNodePath.clearPythonTag('owner')
                hitObject.removeNode()

    def placeBlock(self):
        if self.rayQueue.getNumEntries() > 0:
            self.rayQueue.sortEntries()
            rayHit = self.rayQueue.getEntry(0)
            hitNodePath = rayHit.getIntoNodePath()
            normal = rayHit.getSurfaceNormal(hitNodePath)
            hitObject = hitNodePath.getPythonTag('owner')
            if not hitObject:
                return
            distanceFromPlayer = hitObject.getDistance(self.camera)

            if distanceFromPlayer < 200:
                hitBlockPos = hitObject.getPos()
                newBlockPos = hitBlockPos + normal * self.block_scale
                self.createNewBlock(newBlockPos.x, newBlockPos.y, newBlockPos.z, self.selectedBlockType)

    def updateKeyMap(self, key, value):
        self.keyMap[key] = value

    def captureMouse(self):
        self.cameraSwingActivated = True

        md = self.win.getPointer(0)
        self.lastMouseX = md.getX()
        self.lastMouseY = md.getY()

        properties = WindowProperties()
        properties.setCursorHidden(True)
        properties.setMouseMode(WindowProperties.M_relative)
        self.win.requestProperties(properties)

    def releaseMouse(self):
        self.cameraSwingActivated = False

        properties = WindowProperties()
        properties.setCursorHidden(False)
        properties.setMouseMode(WindowProperties.M_absolute)
        self.win.requestProperties(properties)

    def setupCamera(self):
        self.disableMouse()
        self.camera.setPos(*self.spawnPos)
        self.camLens.setFov(80)

        crosshairs = OnscreenImage(
            image='crosshairs.png',
            pos=(0, 0, 0),
            scale=0.05,
        )
        crosshairs.setTransparency(TransparencyAttrib.MAlpha)

        ray = CollisionRay()
        ray.setFromLens(self.camNode, (0, 0))
        rayNode = CollisionNode('line-of-sight')
        rayNode.addSolid(ray)
        rayNode.setFromCollideMask(BitMask32.bit(1))
        rayNode.setIntoCollideMask(BitMask32.allOff())
        rayNodePath = self.camera.attachNewNode(rayNode)

        self.rayQueue = CollisionHandlerQueue()

        if hasattr(self, 'cTrav'):
            self.cTrav.addCollider(rayNodePath, self.rayQueue)
        else:
            self.cTrav = CollisionTraverser()
            self.cTrav.addCollider(rayNodePath, self.rayQueue)

    def setupSkybox(self):
        skybox = loader.loadModel('skybox/skybox.egg')
        skybox.setScale(500)
        skybox.setBin('background', 1)
        skybox.setDepthWrite(0)
        skybox.setLightOff()
        skybox.reparentTo(render)

    def respawnPlayer(self):
        self.camera.setPos(*self.spawnPos)
        self.playerVelocityZ = 0
        self.grounded = False

game = VoxelEngine()
game.run()