from simcronomicon.town import create_town, draw_town
import matplotlib.pyplot as plt
town = create_town(20, 0.7)
draw_town(town)
plt.show()