# -*- coding: utf-8 -*-
import os
import json
import BigWorld
import GUI
from collections import OrderedDict
from CurrentVehicle import g_currentVehicle
from items import vehicles
import BattleReplay
import Keys
from Avatar import PlayerAvatar
from helpers import dependency
from skeletons.account_helpers.settings_core import ISettingsCore
from PlayerEvents import g_playerEvents
from gui.shared.utils.requesters import REQ_CRITERIA
from gui.shared.utils.requesters.itemsrequester import RequestCriteria, PredicateCondition
#
from OpenModsCore import SimpleConfigInterface
from gui import InputHandler
from gui import g_guiResetters
from gui.mods.gambiter import g_guiFlash, utils
from gui.mods.gambiter.flash import COMPONENT_TYPE, COMPONENT_ALIGN, COMPONENT_EVENT
from gui.mods.gambiter.utils import registerEvent


class SkillHandler(object):
    __slots__ = ('g_tanksMainList', 'maxSkillCount', 'tankmensShownCnt')

    def __init__(self):
        self.g_tanksMainList = OrderedDict()
        self.maxSkillCount = 0
        self.tankmensShownCnt = 0

    def load_session(self):
        config_path = '%s/CrewSkillInformerSession.json' % config_.data['configPath']
        if os.path.getsize(config_path) > 0:
            with open(config_path) as jsonData:
                self.g_tanksMainList = json.load(jsonData)

    def replace_session(self):
        config_path = '%s/CrewSkillInformerSession.json' % config_.data['configPath']
        with open(config_path, 'w+') as outfile:
            outfile.seek(0)
            json.dump(self.g_tanksMainList, outfile, sort_keys=True, indent=4)  # FIXME pickle dump/load
            outfile.truncate()

    def onCurrentVehicleChanged(self, *_):
        vehicle = g_currentVehicle.item
        if not vehicle:
            return

        self.maxSkillCount = 0

        tankDeviceList = OrderedDict()
        installed_devices = vehicle.optDevices.installed.getItems()
        for device in installed_devices:
            if device is not None:
                deviceDescriptor = vehicles.getItemByCompactDescr(device.intCD)
                tankDeviceList[device.intCD] = str(deviceDescriptor.icon[0])

        if config_.withEquipment:
            self.maxSkillCount = len(installed_devices)

        tankmens = g_currentVehicle.itemsCache.items.getTankmen(
            # TANKMAN.NATIVE_TANKS([vehicle.invID])
            REQ_CRITERIA.TANKMAN.IN_TANK | REQ_CRITERIA.TANKMAN.ACTIVE |
            RequestCriteria(PredicateCondition(lambda item: item.vehicleInvID == vehicle.invID))
        )

        tankCrewSkillsList = OrderedDict()

        isAlreadyLoader = False
        brotherHoodCount = 0
        tankmensCount = len(tankmens)

        self.tankmensShownCnt = 0
        for tankman in tankmens.itervalues():
            if tankman.isInTank and tankman.vehicleInvID == vehicle.invID:
                skillCount = len(tankman.skills)
                if skillCount > self.maxSkillCount:
                    self.maxSkillCount = skillCount

                if skillCount > 0:
                    self.tankmensShownCnt += 1

                for skill in tankman.skills:
                    crewMemberSkill = {
                        'name': skill.name,
                        'level': skill.level,
                        'icon': skill.icon
                    }

                    if 'brotherhood' == skill.name and skill.level >= 100:  # Tankman.MAX_SKILL_LEVEL:
                        brotherHoodCount += 1

                    postfix = ''
                    if isAlreadyLoader and tankman.descriptor.role == 'loader':
                        postfix = 'Two'

                    tankmanId = tankman.descriptor.role + postfix
                    if tankmanId in tankCrewSkillsList:
                        tankCrewSkillsList.get(tankmanId).append(crewMemberSkill)
                    else:
                        tankCrewSkillsList[tankmanId] = [crewMemberSkill, ]

                if tankman.descriptor.role == 'loader':
                    isAlreadyLoader = True

        self.g_tanksMainList[vehicle.name] = OrderedDict()
        self.g_tanksMainList[vehicle.name]['crew'] = tankCrewSkillsList
        self.g_tanksMainList[vehicle.name]['devices'] = tankDeviceList
        self.g_tanksMainList[vehicle.name]['brotherhood'] = brotherHoodCount == tankmensCount

        if config_.data['saveSession']:
            self.replace_session()
        return

    def build_main_view(self):
        if not flashController: return
        if BattleReplay.isPlaying(): return

        if not self.g_tanksMainList and config_.data['saveSession']:
            self.load_session()

        if self.g_tanksMainList:
            if not hasattr(BigWorld.player(), 'playerVehicleID'):
                return
            vehicleName = BigWorld.entity(BigWorld.player().playerVehicleID).typeDescriptor.type.name

            if vehicleName in self.g_tanksMainList:
                tankCrewSkillsList = self.g_tanksMainList.get(vehicleName)['crew']
                brotherHoodOk = self.g_tanksMainList.get(vehicleName)['brotherhood']

                priority = {
                    'commander': 1,
                    'gunner': 2,
                    'driver': 3,
                    'radioman': 4,
                    'loader': 5,
                    'loaderTwo': 6
                }

                tankCrewSkillsList = OrderedDict(sorted(tankCrewSkillsList.iteritems(),
                    key=lambda x: priority[x[0]]))

                flashController.add_skills(tankCrewSkillsList, brotherHoodOk)

                if config_.withEquipment:
                    device_name = self.g_tanksMainList.get(vehicleName)['devices']
                    if device_name:
                        flashController.add_equip(device_name)


skill_handler = SkillHandler()
flashController = None
g_playerEvents.onEnqueued += skill_handler.onCurrentVehicleChanged


class Config(SimpleConfigInterface):
    __slots__ = ('ID', 'version', 'author', 'modsGroup', 'modSettingsID', 'save_config', 'buttons', 'data', 'i18n')

    def __init__(self):
        super(Config, self).__init__()

    def init(self):
        self.ID = 'skillInformer'
        self.version = '1.0.0'
        self.author = 'iban'
        self.modsGroup = 'skillInformer'
        self.modSettingsID = 'skillInformer'
        self.save_config = False

        self.buttons = {
            'buttonShow': [Keys.KEY_P],
            'buttonSizeUp': [Keys.KEY_PGUP, [Keys.KEY_LALT, Keys.KEY_RALT]],
            'buttonSizeDown': [Keys.KEY_PGDN, [Keys.KEY_LALT, Keys.KEY_RALT]],
            'buttonReset': [Keys.KEY_DELETE, [Keys.KEY_LCONTROL, Keys.KEY_RCONTROL]],
            'buttonMove': [Keys.KEY_LCONTROL]  # FIXME [Keys.KEY_LCONTROL, Keys.KEY_RCONTROL] check
        }

        self.data = {
            'enabled': True,
            'visible': False,
            'withEquipment': True,
            'saveSession': True,
            'lock': False,
            # 'shadow': True,
            'background': True,
            'background_alpha': 0.5,  # FIXME config
            'sizePercent': 50,
            'font': '$FieldFont',
            'fontSize': 20,
            'color': '0xF8F400',
            'panel': {'x': -230, 'y': 23, 'width': 150, 'height': 150,
                      'alignX': COMPONENT_ALIGN.LEFT, 'alignY': COMPONENT_ALIGN.TOP,
                      'drag': True, 'border': True},  # FIXME add to config
            'img_default': {'width': 48, 'height': 48, 'alpha': 1.0, 'indentX': 10, 'indentY': 20},
            'img': {'width': 48, 'height': 48, 'alpha': 1.0, 'indentX': 10, 'indentY': 20},

            'configPath': 'mods/configs/skillInformer',
            'equipPath': '../maps/icons/artefact',
            'skillsPath': '../maps/icons/battlePass/tooltips/icons',
            'tankmanPath': '../maps/icons/tankmen/roles/big',
            'panel_bgPath': '../maps/icons/windows/window_bg/centered.png',
            'equip_mainPath': '../maps/icons/artefact/empty.png',
            'skill_lockPath': '../maps/icons/components/countdown/lock.png',

            'buttonShow': self.buttons['buttonShow'],
            'buttonSizeUp': self.buttons['buttonSizeUp'],
            'buttonSizeDown': self.buttons['buttonSizeDown'],
            'buttonReset': self.buttons['buttonReset'],
            'buttonMove': self.buttons['buttonMove'],  # static

            'skills_ness_complete': [
                'commander_expert', 'commander_sixthSense', 'driver_tidyPerson', 'gunner_rancorous',
                'gunner_sniper', 'loader_desperado', 'loader_intuition', 'loader_pedant', 'radioman_lastEffort'
            ],
        }
        self.i18n = {
            'version': self.version,
            'UI_description': 'skillInformer',
            'UI_setting_buttonShow_text': 'Button Show',
            'UI_setting_buttonShow_tooltip': '',
            'UI_setting_saveSession_text': 'Save session',
            'UI_setting_saveSession_tooltip': 'Used when your relaunch game and return to battle',
            'UI_setting_withEquipment_text': 'Show equipment',
            'UI_setting_withEquipment_tooltip': 'show equipment in battle',
            'UI_setting_lock_text': 'Lock panel',
            'UI_setting_lock_tooltip': 'Lock panel for movement',
            # 'UI_setting_shadow_text': 'Shadow panel',
            # 'UI_setting_shadow_tooltip': 'Shadow panel',
            'UI_setting_background_text': 'Show background',
            'UI_setting_background_tooltip': 'Will add image background to panel',
            'UI_setting_ImageAlpha_text': 'Image Alpha',
            'UI_setting_ImageAlpha_tooltip': 'Image transparency from 0 to 1',
            'UI_setting_sizePercent_text': 'Size Percent',
            'UI_setting_sizePercent_tooltip': '',
            'UI_setting_buttonSizeUp_text': 'Button size up',
            'UI_setting_buttonSizeUp_tooltip': '',
            'UI_setting_buttonSizeDown_text': 'Button size down',
            'UI_setting_buttonSizeDown_tooltip': '',
            'UI_setting_buttonReset_text': 'Button: Reset Settings',
            'UI_setting_buttonReset_tooltip': '',
        }
        print '[LOAD_MOD]:  [%s %s, %s]' % (self.ID, self.version, self.author)
        super(Config, self).init()

    def createTemplate(self):
        return {
            'modDisplayName': self.i18n['UI_description'],
            'enabled': self.data['enabled'],
            'column1': [
                self.tb.createControl('background'),
                self.tb.createControl('saveSession'),
                self.tb.createControl('withEquipment'),
                self.tb.createControl('lock'),
                # self.tb.createControl('shadow'),
            ],
            'column2': [
                self.tb.createHotKey('buttonShow'),
                self.tb.createHotKey('buttonSizeUp'),
                self.tb.createHotKey('buttonSizeDown'),
                self.tb.createHotKey('buttonReset'),
                self.tb.createStepper('sizePercent', 10, 100, 10, False),
            ]
        }

    @property
    def withEquipment(self):
        return self.data['withEquipment']


SPECIAL_TO_KEYS = {
     -1: ['LALT', 'RALT'],  # 56  184  -4
     -2: ['LCONTROL', 'RCONTROL'],  # 29  157   -2
     -3: ['LSHIFT', 'RSHIFT']  # 42  54  his -1
 }

modify_keys = {'LALT', 'RALT', 'LCONTROL', 'RCONTROL', 'LSHIFT', 'RSHIFT'}
# LCONTROL 29  RCONTROL 157
# LSHIFT 42  RSHIFT 54
# LALT 56  RALT 184


def checkKeysDown(keys, event, modifiers):  # FIXME не отлавливает нажатие модификатора при зажатой клавише
    if event and BigWorld.isKeyDown(event.key):
        keys_orig = []
        keys_modifiers = []

        for key in keys:
            # FIXME переделать на массив
            # keySets = [data if not isinstance(data, int) else (data,) for data in keys]
            if key in SPECIAL_TO_KEYS:
                keys_modifiers.append(key)
            else:
                keys_orig.append(key)
        return (
                bool(keys) and all(BigWorld.isKeyDown(x) for x in keys)
                and (event.key in keys)
                and (not bool(keys_modifiers) or bool(modifiers) and all(modif in modifiers for modif in keys_modifiers))
                )
    return False


def checkKeysUp(keys, event, modifiers):
    if event and event.isKeyUp():
        keys_orig = []
        keys_modifiers = []
        for key in keys:
            if key in SPECIAL_TO_KEYS or BigWorld.keyToString(key) in modify_keys:
                keys_modifiers.append(key)
            else:
                keys_orig.append(key)

        if BigWorld.keyToString(event.key) in modify_keys:
            print 'modifier main key', keys_orig, keys_modifiers, modify_keys
            print bool(keys) and (not bool(keys_orig) or all(BigWorld.isKeyDown(x) for x in keys_orig))
            print bool(keys_modifiers) and bool(modifiers) and all(x in modifiers for x in keys_modifiers)

            return (bool(keys)
                    and (not bool(keys_orig) or all(BigWorld.isKeyDown(x) for x in keys_orig))
                    and bool(keys_modifiers) and bool(modifiers) and all(x in modifiers for x in keys_modifiers)
                    )

        return (bool(keys) and event.key in keys
                and (not bool(keys_modifiers) or all(BigWorld.isKeyDown(x) for x in keys_modifiers))
                and (not bool(keys_modifiers) or bool(modifiers) and all(x in modifiers for x in keys_modifiers))
                )
    return False


class FlashController(object):
    __slots__ = ('ID', 'items')
    settingsCore = dependency.descriptor(ISettingsCore)

    def __init__(self, ID):
        self.ID = ID
        self.items = OrderedDict()

    def startBattle(self):
        if not config_.data['enabled']: return
        if BattleReplay.isPlaying(): return

        InputHandler.g_instance.onKeyDown += self.onKeyDown
        InputHandler.g_instance.onKeyUp += self.onKeyDown

        self.items = OrderedDict()

        COMPONENT_EVENT.UPDATED += self.update
        config_.data['visible'] = False
        width = config_.data['panel']['width']
        height = config_.data['panel']['height']

        panel_data = {
            'x': config_.data['panel']['x'], 'y': config_.data['panel']['y'],
            'alignX': config_.data['panel']['alignX'], 'alignY': config_.data['panel']['alignY'],
            'drag': config_.data['panel']['drag'], 'border': config_.data['panel']['border'],
        }

        g_guiFlash.createComponent(self.ID, COMPONENT_TYPE.PANEL, panel_data)

        if config_.data['background']:
            g_guiFlash.createComponent(self.ID + '.bg', COMPONENT_TYPE.IMAGE, {
                'image': config_.data['panel_bgPath'],
                'alpha': config_.data['background_alpha'], 'width': width, 'height': height,
                'alignX': COMPONENT_ALIGN.CENTER, 'alignY': COMPONENT_ALIGN.TOP
            })

        g_guiResetters.add(self.screenResize)
        self.setVisible(False)
        self.setupSize()

    def endBattle(self):
        if not config_.data['enabled']: return
        InputHandler.g_instance.onKeyDown -= self.onKeyDown
        InputHandler.g_instance.onKeyUp -= self.onKeyDown
        COMPONENT_EVENT.UPDATED -= self.update
        g_guiResetters.remove(self.screenResize)
        self.removeComponents()
        if config_.save_config:
            config_.writeDataJson()
            config_.save_config = False

    def add_skills(self, skills, brotherHoodOk):
        icon = config_.data['img']
        width, height, alpha, indentX, indentY = icon['width'], icon['height'], icon['alpha'], icon['indentX'], icon['indentY']

        for idy, (tankman_name, skills) in enumerate(skills.iteritems()):
            idx = 0
            y = (height + indentY) * idy

            name = tankman_name
            if tankman_name.endswith('Two'):
                name = tankman_name[:-3]
            tankman_img_path = '%s/%s.png' % (config_.data['tankmanPath'], name)

            g_guiFlash.createComponent(self.ID + '.%s%s' % (idx, idy), COMPONENT_TYPE.IMAGE, {
                'image': tankman_img_path,
                'x': indentX, 'y': y, 'tooltip': tankman_name,
                'alpha': alpha, 'width': width, 'height': height
            })
            items = OrderedDict({idx: {'type': 'image'}})

            for idx, skill in enumerate(skills, 1):
                x = (width + indentX) * idx + indentX
                img_data = {
                    'image': '%s/icon_perk_%s' % (config_.data['skillsPath'], skill['icon']),
                    'x': x, 'y': y, 'tooltip': skill['name'],
                    'alpha': alpha, 'width': width, 'height': height}

                g_guiFlash.createComponent(self.ID + '.%s%s' % (idx, idy), COMPONENT_TYPE.IMAGE, img_data)
                items[idx] = {'type': 'image'}

                if ((skill['name'] == 'brotherhood' and not brotherHoodOk) or
                    (skill['level'] < 100 and skill['name'] in config_.data['skills_ness_complete'])):
                    img_data['image'] = config_.data['skill_lockPath']
                    img_data['alpha'] = 0.95
                    img_data['tooltip'] = skill['name'] + " don't work"  # FIXME add to config
                    g_guiFlash.createComponent(self.ID + '.%s%s' % (-idx, idy), COMPONENT_TYPE.IMAGE, img_data)
                    items[-idx] = {'type': 'image_over'}

                if skill['level'] < 100:
                    props = {
                        'type': 'text',
                        'text_raw': '<font face="{font}" size="{{}}" color="{color}" vspace="-3" align="baseline">{text}</font>'.format(
                            font=config_.data['font'], color=config_.data['color'], text=str(skill['level']) + '%')
                    }
                    g_guiFlash.createComponent(self.ID + '.%s%s' % (idx+1, idy), COMPONENT_TYPE.LABEL, {
                        'text': props['text_raw'].format(int(config_.data['fontSize'] * config_.data['sizePercent'] / 100.0)),
                        'x': x + width, 'y': y + indentY / 2.0,
                        'alpha': alpha, 'width': width, 'height': height,
                        # 'shadow': {             # FIXME config  shadow_text
                        #     'distance': 0, 'angle': 0, 'color': 0x000000, 'alpha': 90, 'blurX': 1, 'blurY': 1,
                        #     'strength': 3000, 'quality': 1
                        # }
                    })

                    items[idx+1] = props
            self.items[idy] = items

    def add_equip(self, equip):
        icon = config_.data['img']
        width, height, alpha, indentX, indentY = icon['width'], icon['height'], icon['alpha'], icon['indentX'], icon['indentY']

        idy = 0
        if self.items:
            idy = next(reversed(self.items)) + 1

        idx = 0
        y = (height + indentY) * idy

        g_guiFlash.createComponent(self.ID + '.%s%s' % (idx, idy), COMPONENT_TYPE.IMAGE, {
            'image': config_.data['equip_mainPath'], 'x': indentX, 'y': y,
            'alpha': alpha, 'width': width, 'height': height, 'tooltip': 'equipment'}
        )

        items = OrderedDict({idx: {'type': 'image'}})

        for idx, equip_name in enumerate(equip.itervalues(), 1):
            equip_icon = '%s/%s.png' % (config_.data['equipPath'], equip_name)
            x = (width + indentX) * idx + indentX

            g_guiFlash.createComponent(self.ID + '.%s%s' % (idx, idy), COMPONENT_TYPE.IMAGE, {
                'image': equip_icon, 'x': x, 'y': y,
                'alpha': alpha, 'width': width, 'height': height, 'tooltip': equip_name}
            )
            items[idx] = {'type': 'image'}
        self.items[idy] = items

    def setVisible(self, visible):
        data = {'visible': visible}
        g_guiFlash.updateComponent(self.ID, data)
        if config_.data['background']:
            g_guiFlash.updateComponent(self.ID + '.bg', data)
        for idy, idx_od in self.items.iteritems():
            for idx in idx_od.iterkeys():
                g_guiFlash.updateComponent(self.ID + '.%s%s' % (idx, idy), data)

    def removeComponents(self):
        g_guiFlash.deleteComponent(self.ID)
        if config_.data['background']:
            g_guiFlash.deleteComponent(self.ID + '.bg')
        for idy, idx_od in self.items.iteritems():
            for idx in idx_od.iterkeys():
                g_guiFlash.deleteComponent(self.ID + '.%s%s' % (idx, idy))
        self.items = OrderedDict()

    def onKeyDown(self, event):
        if not config_.data['enabled']: return
        player = BigWorld.player()
        if not player.arena: return

        modifiers = set()
        if event.isAltDown(): modifiers.add(-1)  # -4
        if event.isCtrlDown(): modifiers.add(-2)  # -2
        if event.isShiftDown(): modifiers.add(-3)  # -1

        if checkKeysUp(config_.data['buttonShow'], event, modifiers):
            self.setVisible(False)

        if checkKeysDown(config_.data['buttonShow'], event, modifiers):
            self.setVisible(True)

        if checkKeysUp(config_.data['buttonMove'], event, modifiers):
            print 'buttonMove checkKeysUp'
            if not config_.data['lock']:
                self.setVisible(False)

        if checkKeysDown(config_.data['buttonMove'], event, modifiers):
            if not config_.data['lock']:
                self.setVisible(True)

        if checkKeysDown(config_.data['buttonSizeDown'], event, modifiers):
            if not config_.data['lock']:
                config_.data['sizePercent'] = max(10, config_.data['sizePercent'] - 10)
                self.setupSize()
                config_.save_config = True

        if checkKeysDown(config_.data['buttonSizeUp'], event, modifiers):
            if not config_.data['lock']:
                config_.data['sizePercent'] = min(config_.data['sizePercent'] + 10, 100)
                self.setupSize()
                config_.save_config = True

        if checkKeysDown(config_.data['buttonReset'], event, modifiers):
            if not config_.data['lock']:
                config_.data['sizePercent'] = 50
                # FIXME reset position and so on
                self.setupSize()
                # config_.writeDataJson()
                config_.save_config = True

    def update(self, alias, props):
        if str(alias) == str(config_.ID):
            x = props.get('x', config_.data['panel']['x'])
            if x and x != config_.data['panel']['x']:
                config_.data['panel']['x'] = x
            y = props.get('y', config_.data['panel']['y'])
            if y and y != config_.data['panel']['y']:
                config_.data['panel']['y'] = y
            self.setupSize()
            config_.save_config = True

    @staticmethod
    def screenFix(screen, value, mod, align=1):
        if align == 1:
            if value + mod > screen:
                return max(0, int(screen - mod))
            if value < 0:
                return 0
        if align == -1:
            if value - mod < -screen:
                return min(0, int(-screen + mod))
            if value > 0:
                return 0
        if align == 0:
            scr = screen / 2
            if value < scr:
                return int(scr - mod)
            if value > -scr:
                return int(-scr)
        return None

    def screenResize(self):
        curScr = GUI.screenResolution()
        scale = self.settingsCore.interfaceScale.get()
        xMo, yMo = curScr[0] / scale, curScr[1] / scale
        panel_data = {}
        x = None
        if config_.data['panel']['alignX'] == COMPONENT_ALIGN.LEFT:
            x = self.screenFix(xMo, config_.data['panel']['x'], config_.data['panel']['width'], 1)
        if config_.data['panel']['alignX'] == COMPONENT_ALIGN.RIGHT:
            x = self.screenFix(xMo, config_.data['panel']['x'], config_.data['panel']['width'], -1)
        if config_.data['panel']['alignX'] == COMPONENT_ALIGN.CENTER:
            x = self.screenFix(xMo, config_.data['panel']['x'], config_.data['panel']['width'], 0)
        if x is not None:
            if x != int(config_.data['panel']['x']):
                config_.data['panel']['x'] = x
                panel_data['x'] = x

        y = None
        if config_.data['panel']['alignY'] == COMPONENT_ALIGN.TOP:
            y = self.screenFix(yMo, config_.data['panel']['y'], config_.data['panel']['height'], 1)
        if config_.data['panel']['alignY'] == COMPONENT_ALIGN.BOTTOM:
            y = self.screenFix(yMo, config_.data['panel']['y'], config_.data['panel']['height'], -1)
        if config_.data['panel']['alignY'] == COMPONENT_ALIGN.CENTER:
            y = self.screenFix(yMo, config_.data['panel']['y'], config_.data['panel']['height'], 0)
        if y is not None:
            if y != int(config_.data['panel']['y']):
                config_.data['panel']['y'] = y
                panel_data['y'] = y
        g_guiFlash.updateComponent(self.ID, panel_data)

    def setupSize(self, h=None, w=None):
        img_height = config_.data['img_default'].get('height', 48.0)
        img_width = config_.data['img_default'].get('width', 48.0)
        indentX = config_.data['img_default'].get('indentX', 10.0)
        indentY = config_.data['img_default'].get('indentY', 20.0)
        mult = config_.data['sizePercent'] / 100.0

        config_.data['img']['height'] = img_height = int(img_height * mult)
        config_.data['img']['width'] = img_width = int(img_width * mult)
        config_.data['img']['indentX'] = indentX = max(1, int(indentX * mult))
        config_.data['img']['indentY'] = indentY = max(2, int(indentY * mult))

        panel_height = (skill_handler.tankmensShownCnt + 1 if config_.withEquipment else 0) * (img_height + indentY)
        panel_width = (skill_handler.maxSkillCount + 2) * (img_width + indentX)

        config_.data['panel']['height'] = panel_height
        config_.data['panel']['width'] = panel_width

        data = {'height': img_height, 'width': img_width, 'x': 0, 'y': 0}

        for idy, idx_od in self.items.iteritems():
            data['y'] = (img_height + indentY) * idy

            for idx, props in idx_od.iteritems():
                if idx >= 0:
                    data['x'] = (img_width + indentX) * idx + indentX

                if props['type'] == 'text':
                    text_data = data.copy()
                    text_data['text'] = props['text_raw'].format(str(int(config_.data['fontSize'] * mult)))
                    text_data['y'] = data['y'] + img_height / 2
                    g_guiFlash.updateComponent(self.ID + '.%s%s' % (idx, idy), text_data)
                else:
                    g_guiFlash.updateComponent(self.ID + '.%s%s' % (idx, idy), data)

        data = {'height': panel_height, 'width': panel_width}
        g_guiFlash.updateComponent(self.ID, data)
        if config_.data['background']:
            g_guiFlash.updateComponent(self.ID + '.bg', data)

        self.screenResize()


config_ = Config()
flashController = FlashController(config_.ID)


@registerEvent(PlayerAvatar, '_PlayerAvatar__startGUI')
def new_PlayerAvatar__startGUI(_):
    skill_handler.build_main_view()
    flashController.startBattle()



@registerEvent(PlayerAvatar, '_PlayerAvatar__destroyGUI')
def new_PlayerAvatar__destroyGUI(_):
    flashController.endBattle()


