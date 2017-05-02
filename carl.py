from multiprocessing import Process
import cloud_sender
import display_manager as display
import temp_controller
import temp_monitor
import command_receiver

if __name__ == '__main__':
    display.print_text("********************", lin=0, col=0, clear=True)
    display.print_text("* Iniciando IoBeer *", lin=1, col=0)
    display.print_text("*                  *", lin=2, col=0)
    display.print_text("********************", lin=3, col=0)

    display.print_text("* \xff\xff               *", lin=2, col=0)

    p1 = Process(target=command_receiver.start_command_reicever)
    p1.start()

    display.print_text("* \xff\xff\xff\xff             *", lin=2, col=0)
    p2 = Process(target=cloud_sender.start_sender)
    p2.start()

    display.print_text("* \xff\xff\xff\xff\xff\xff           *", lin=2, col=0)
    p3 = Process(target=temp_controller.start_controller)
    p3.start()

    display.print_text("* \xff\xff\xff\xff\xff\xff\xff\xff\xff\xff       *", lin=2, col=0)
    p4 = Process(target=temp_monitor.start_monitor)
    p4.start()

    display.print_text("* \xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff  *", lin=2, col=0)
    p5 = Process(target=display.start_display)
    p5.start()

    p4.join()
