import switchmate
import time
t = time.time()
x = switchmate.Switch()
x.turn_on()
x.turn_off()
#x.switch()
#x.switch()
print(time.time()-t)
