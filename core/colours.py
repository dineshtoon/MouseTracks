from __future__ import division, absolute_import

from core.compatibility import range


COLOURS_MAIN = {
    'red': (255, 0, 0, 255),
    'green': (0, 255, 0, 255),
    'blue': (0, 0, 255, 255),
    'yellow': (255, 255, 0, 255),
    'cyan': (0, 255, 255, 255),
    'magenta': (255, 0, 255, 255),
    'white': (255, 255, 255, 255),
    'grey': (127, 127, 127, 255),
    'gray': (127, 127, 127, 255),
    'black': (0, 0, 0, 255),
    'orange': (255, 127, 0, 255),
    'pink': (255, 0, 127, 255),
    'purple': (127, 0, 255, 255),
    'sky': (0, 164, 255, 255)
}

COLOUR_MODIFIERS = {
    #name: (add, multiply, alpha)
    'light': (128, 0.5, 1.0),
    'dark': (0, 0.5, 1.0),
    'transparent': (0, 1.0, 0.0),
    'translucent': (0, 1.0, 0.5),
    'opaque': (0, 1.0, 2.0)
}


class ColourRange(object):
    """Make a transition between colours.
    All possible colours within the range are cached for quick access.
    """
    
    def __init__(self, min_amount, max_amount, colours, offset=0, loop=False, cache=None):
        
        if min_amount >= max_amount:
            colours = [colours[0]]
            max_amount = min_amount + 1
        self.amount = (min_amount, max_amount)
        self.amount_diff = max_amount - min_amount
        self.colours = colours
        self.offset = offset
        self.loop = loop
        self._len = len(colours)
        self._len_m = self._len - 1

        self._step_max = 255 * self._len
        self._step_size = self.amount_diff / self._step_max
        
        #Cache results for quick access
        if cache is None:
            self.cache = []
            for i in range(self._step_max + 1):
                self.cache.append(self.calculate_colour(self.amount[0] + i * self._step_size))
        else:
            self.cache = cache
            
    def __getitem__(self, n):
        """Read an item from the cache."""
        value_index = int((n - self.amount[0]) / self._step_size)
        if self.loop:
            if value_index != self._step_max:
                return self.cache[value_index % self._step_max]
        return self.cache[min(max(0, value_index), self._step_max)]
    
    def calculate_colour(self, n, as_int=True):
        """Calculate colour for given value."""
        offset = (n + self.offset - self.amount[0]) / self.amount_diff
        index_f = self._len_m * offset

        #Calculate the indexes of colours to mix
        index_base = int(index_f)
        index_mix = index_base + 1
        if self.loop:
            index_base %= self._len
            index_mix %= self._len
        else:
            index_base = max(min(index_base, self._len_m), 0)
            index_mix = max(min(index_mix, self._len_m), 0)

        #Mix colours
        base_colour = self.colours[index_base]
        mix_colour = self.colours[index_mix]
        mix_ratio = max(min(index_f - index_base, 1), 0)
        mix_ratio_r = 1 - mix_ratio

        #Generate as tuple
        if as_int:
            return tuple(int(i * mix_ratio_r + j * mix_ratio)
                         for i, j in zip(base_colour, mix_colour))
        else:
            return tuple(i * mix_ratio_r + j * mix_ratio for i, j in zip(base_colour, mix_colour))

def _parse_colour_text(colour_name):
    """Convert text into a colour map.
    It could probably do with a rewrite to make it more efficient,
    as it was first written to only use capitals.

    Mixed Colour:
        Combine multiple colours.
        Examples: BlueRed, BlackYellowGreen
    Modified Colour:
        Apply a modification to a colour.
        If multiple ones are applied, they will work in reverse order.
        Light and dark are not opposites so will not cancel each other out.
        Examples: LightBlue, DarkLightYellow
    Transition:
        This ends the current colour mix and starts a new one.
        Examples: BlackToWhite, RedToGreenToBlue
    Any number of these features can be combined together to create different effects.
        
    As an example, here are the values that would result in the heatmap:
        BlackToDarkBlueToBlueToCyanBlueBlueBlueToCyanBlueToCyan
        + CyanCyanBlueToCyanCyanCyanYellowToCyanYellowToCyan
        + YellowYellowYellowToYellowToOrangeToRedOrangeToRed 
    """
    colours = {'Final': [],
               'Temp': [],
               'Mult': []}
    word = ''
    i = 0
    
    #Loop letters until end of word has been reached
    while True:
        done_stuff = False
        skip = False
        try:
            letter = colour_name[i]
        except IndexError:
            try:
                letter = colour_name[i - 1]
            except IndexError:
                break
            skip = True

        if letter in 'abcdefghijklmnopqrstuvwxyz':
            word += letter
            done_stuff = True

        word_colours = word in COLOURS_MAIN
        word_mods = word in COLOUR_MODIFIERS
        word_to = word == 'to'
        
        #Build colours
        if skip or word_colours or word_mods or word_to or letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            
            if word_mods:
                colours['Mult'].append(COLOUR_MODIFIERS[word])
            elif word_colours:
                colours['Temp'].append(list(COLOURS_MAIN[word]))

                #Apply modifiers
                for mult in colours['Mult'][::-1]:
                    alpha = colours['Temp'][-1].pop()
                    colours['Temp'][-1] = [mult[0] + mult[1] * c for c in colours['Temp'][-1]]
                    colours['Temp'][-1] += [min(255, alpha * mult[2])]
                colours['Mult'] = []

            #Merge colours together
            if word_to or skip:
                num_colours = len(colours['Temp'])
                joined_colours = tuple(sum(c) / num_colours for c in zip(*colours['Temp']))
                colours['Final'].append(joined_colours)
                colours['Temp'] = []
                
            if not done_stuff:
                word = letter.lower()
            else:
                word = ''
            done_stuff = True
                
        i += 1
        if not done_stuff:
            raise ValueError('invalid characters in colour map')
            
    return tuple(colours['Final'])


class ColourMap(object):
    """Look up default colours or generate one if the set doesn't exist."""
    _MAPS = {
        'jet': ('BlackToDarkBlueToBlueToCyanBlueBlueBlueToCyanBlueTo'
                'CyanCyanCyanBlueToCyanCyanCyanYellowToCyanYellowTo'
                'CyanYellowYellowYellowToYellowToOrangeToRedOrangeToRed'), #heatmap
        'transparentjet': ('TransparentBlackToTranslucentTranslucentDarkBlueTo'
                           'TranslucentBlueToTranslucentCyanTranslucentBlueBlueBlueTo'
                           'CyanBlueToCyanCyanCyanBlueToCyanCyanCyanYellowToCyanYellow'
                           'ToCyanYellowYellowYellowToYellowToOrangeToRedOrangeToRed'), #heatmap
        'radiation': 'BlackToRedToYellowToWhiteToWhiteWhiteWhiteLightLightGrey', #heatmap
        'transparentradiation': ('TransparentBlackToTranslucentRedToYellowTo'
                                 'WhiteToWhiteWhiteWhiteLightLightGrey'), #heatmap
        'default': 'WhiteToBlack', #tracks
        'citrus': 'BlackToDarkDarkGreyToDarkGreenToYellow', #tracks
        'ice': 'BlackToDarkBlueToDarkBlueLightDarkCyanToLightBlueDarkCyanToWhite', #tracks
        'neon': 'BlackToPurpleToPinkToBlackToPink', #tracks
        'sunburst': 'DarkDarkGrayToOrangeToBlackToOrangeToYellow', #tracks
        'demon': 'WhiteToRedToBlackToWhite', #tracks
        'chalk': 'BlackToWhite', #tracks
        'lightning': 'DarkPurpleToLightMagentaToLightGrayToWhiteToWhite', #tracks
        'hazard': 'WhiteToBlackToYellow', #tracks
        'razer': 'BlackToDarkGreyToBlackToDarkGreenToGreenToBlack', #tracks
        'sketch': 'LightGreyToBlackToDarkPurpleToWhiteToLightGreyToBlackToBlue', #tracks
        'grape': 'WhiteToBlackToMagenta', #tracks
        'spiderman': 'RedToBlackToWhite', #tracks/keyboard
        'shroud': 'GreyToBlackToLightPurple', #tracks
        'blackwidow': 'PurpleToLightCyanWhiteToPurpleToBlack', #tracks
        'aqua': 'WhiteToWhiteWhiteLightCyanSkyToSkyToSkyBlue', #keyboard
        'fire': ('WhiteToWhiteWhiteYellowLightOrangeToWhiteYellowLightOrangeToWhiteYellowOrangeTo'
                 'WhiteLightYellowRedLightRedOrangeToYellowLightYellowRedDarkOrangeToRedDarkRedDarkRed'), #keyboard
        'fire3': ('WhiteToWhiteWhiteYellowLightOrangeToWhiteYellowLightOrangeToWhiteYellow'
                 'OrangeToLightRedOrangeOrangeToLightYellowRedDarkOrangeToRedDarkRedDarkRed'), #keyboard
        'fire2': ('WhiteToWhiteWhiteYellowLightOrangeToWhiteYellowLightOrangeToWhiteYellow'
                 'OrangeToLightRedOrangeOrangeToLightYellowRedRedDarkOrangeToDarkRed'), #keyboard
        'ivy': 'WhiteToBlueGreenGreenToBlack', #keyboard
        'matrix': ('BlackBlackBlackBlackDarkGreenDarkDarkGreyToBlackBlack'
                   'BlackBlackBlackGreyGreenToBlackBlackDarkGreyGreenToGreen'), #keyboard/tracks
        'nature': ('WhiteToWhiteLightYellowLightGreenLightLightGrey' #keyboard
                   'ToLightYellowGreenLightGreenToDarkGreen'), #keyboard
        'linearfire': 'WhiteToYellowLightOrangeToLightYellowOrangeRedDarkRedToDarkOrangeOrangeRedToBlackBlackOrangeRedDarkRedToRedDarkRedDarkRed',  #keyboard (linear) - need to make the process automatic
        'linearmatrix': 'BlackBlackBlackBlackBlackDarkGreenDarkDarkGreyToGreen',
        'linearnature': 'WhiteToDarkGreen'
    }
    def __getitem__(self, colour_profile):
        try:
            return _parse_colour_text(self._MAPS[colour_profile.lower()])
        except KeyError:
            generated_map = _parse_colour_text(colour_profile)
            if generated_map:
                if len(generated_map) < 2:
                    raise ValueError('not enough colours to generate colour map')
                return generated_map
            else:
                raise ValueError('unknown colour map')


def get_luminance(r, g, b, a=None):
    return (0.2126*r + 0.7152*g + 0.0722*b)

    
def _new_colour_map_data():
    return {'tracks': False, 'clicks': False, 'keyboard': False}

    
def parse_colour_file(path):
    with open(path, 'r') as f:
        data = f.read()
        
    colour_maps = {}
    for line in data.splitlines():
        var, value = [i.strip() for i in line.split('=', 1)]
        var_parts = var.split('.')[1:]
        map_name = var_parts[0].lower()
        var_type = var_parts[1]

        #Write values to dictionary
        if map_name not in colour_maps:
            colour_maps[map_name] = _new_colour_map_data()
        if var_type in ('tracks', 'clicks', 'keyboard'):
            value = True if value.lower() == 'true' else False
        colour_maps[map_name][var_type] = value

        #Link alternative names
        if var_type == 'map':
            alt_name = ''.join(var_parts[2:][::-1]).strip() + map_name
            if alt_name:
                colour_maps[alt_name] = colour_maps[map_name]

    return colour_maps
