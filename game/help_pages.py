import game.color as color
import random

# let's say 66 x 35, so here's a width ruler
# trim the first \n when printing
############################################################
# rewriting with wider panels, headers, and coloring
# $titles, ^colors^

##################################################################
basics = ("""
...................  $Movement + Environment$
.                 .
.                 .   You are the ^@^. The ^letters^ on the map are
.  $YKU   \\↑/$      .   other people.
.  $H.L = ← →$      .
.  $BJN   /↓\\$      .   Move with the vim keys (shown here) or the
.                 .   num pad.
.  $YU      \\/$     .   
.   $HJKL =  ←↓↑→$  .   Press $.$ or $5$ to wait.
.  $BN      /\\$     .   
.                 .   Move into a person to perform an action on
.                 .   them (either EAT or TALK, shown in the top
...................   right of the screen).

$Eating, Transforming, and Dying$

You start off in the restroom next to an unsuspecting victim. $Move$
$into them$ to eat them and take on their identity. This takes a few
turns -- $wait in place$ to complete the process. Moving away will
interrupt it.

Once you've taken on a ^human^ identity, your schedule will show
your name and where the other ^humans^ expect you to be. If you
don't show, you may cause some distress.

As a ^human^, you may press $TAB$ to change your bump action (top
right of the screen). Eating as a human transforms you back into a
changeling temporarily, so do it in privacy when possible.

As time passes, your ^VIGOR^ will decrease. Eat a human to fully
restore your ^VIGOR^. If your ^VIGOR^ depletes fully, you die.

Getting tazed will also drastically decrease your ^VIGOR^. More on
that in the "humans" tab.
""",[color.changeling, color.npc, color.npc, color.npc, color.npc, color.changeling, color.changeling, color.changeling, color.changeling])
##################################################################
#d=36


##################################################################
goal = ("""
$The Shuttle$

Somewhere in this facility is a shuttle leading out into the wider
world. The people here are discerning and suspicious, but $out$
$there$, they are gullible and ^fat^. Perfect prey!

The Shuttle has 3 main lines of defense:

    1. It's $locked$. Someone in the facility has the key.

    2. It has a $bioscanner$. If you try to board the shuttle while
       the bioscanner is operational, it'll taze you to death.
       It must be dismantled.

    3. It's $guarded$. Someone is always nearby and they'll take
       issue with you messing around near the shuttle.

Solve these problems and get in the shuttle for a golden future!

On the other hand, if the humans get too nervous, they'll call an
^evacuation^. They'll board their pretty shuttle and leave you
behind to starve! Avoid their suspicion at all costs.
""",[color.changeling,color.dark_red])
##################################################################
#d=36


##################################################################
ui = ("""
$Look$

The SURROUNDINGS panel shows you which room you're in and who's
nearby. Hit the letter next to a name [eg, if you see ^A) Bob^,
hit Shift+A] for more info on that person.

You can also click any tile on the map for more info on whatever's 
in that tile.


$Listen$

The LOG panel will show you what people are saying and what's
happening around you. This is important! Keep your eyes peeled
for signs of unrest and suspicion.


$Lick$

The top right panel shows what will happen if you bump into a
human. When you are a changeling, it's stuck on ^EAT^, but as a
human you can change your selection with the TAB key.


$Leg It$

The SCHEDULE panel shows where you need to be and when. The
current time is displayed above your ID, and your current
shift is $highlighted$.
""",[color.npc, color.dark_red])
##################################################################
#d=36

##################################################################
humans = ("""
You may wish to discover how the humans act on your own! Skip this
panel to avoid spoilers.

$Investigations$

When humans go missing, those that share a shift with them notice.
After sufficient time, a human will launch an investigation and
try to find the missing person. 

If the person isn't found within a day, the investigator will 
announce this to the crew and initiate ^evacuation^ protocols.


$Sightings$

If you're seen in your true form, whoever sees you will announce
it. Others will rush to where you are to confirm the sighting. 
Once one other person confirms the sighting, that's it. ^Evacuation^
time. Fortunately, sightings are debunked just as easily.


$Schedules$

When they aren't tracking you down, humans just follow their 
schedules. Follow yours to dodge suspicion!
""",[color.dark_red, color.dark_red])
##################################################################
#d=36

##################################################################
other = ("""

""",[])
##################################################################
#d=36
