from . import rd

class Folk:
    def __init__(self, address, status):
        self.address = address
        self.social_energy = rd.randint(4, 10)
        self.status = status
        self.spreader_streak = 0
    
    def convert(self, old_stat, new_stat, counter_t):
        """Convert the rumor spreading status of a person and update the counter of population with each status
        of the current time step"""
        self.status = new_stat
        counter_t[old_stat] -= 1
        counter_t[new_stat] += 1
        if old_stat == 'S':
            self.spreader_streak = 0 # Reset spreader streak

    def interact(self, other_person, counter_t, params):
        self.social_energy -= 1
        dice = rd.random()

        # Rule 4.1
        if self.status == 'S' and other_person.status not in ['Ir', 'Is'] and dice > params.S2R:
            self.convert('S', 'R', counter_t)
        elif other_person.status == 'S':
            # Rule 1
            if self.status == 'Ir' and dice > params.Ir2S:
                self.convert('Ir', 'S', counter_t)
            # Rule 2
            elif self.status == 'Is':
                if dice > params.Is2S:
                    self.convert('Is', 'S', counter_t)
                else:
                    if dice > params.Is2E:
                        self.convert('Is', 'E', counter_t)
            # Rule 3.1
            elif self.status == 'E' and dice > params.E2S:
                self.convert('E', 'S', counter_t)
        # Rule 3.2
        elif other_person.status == 'R' and self.status == 'E' and dice > params.E2R:
            self.status = 'R'
    
    def sleep(self, counter_t, params):
        if self.status == 'S':
            # Rule 4.2: Forgetting mechanism
            if params.mem_span < self.spreader_streak or rd.random() > params.forget:
                self.convert('S', 'R', counter_t)
            else:
                self.spreader_streak += 1

    def __repr__(self):
        return f"Person live at ({self.address}, Social Energy={self.social_energy}, Status={self.status})"