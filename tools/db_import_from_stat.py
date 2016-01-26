#!/usr/bin/env python

import argparse
import halo_db as db
from halo_db import halo_stat_files as hsf, cached_writer as cw, parallel_tasks as pt

def run():

    parser = argparse.ArgumentParser()
    db.supplement_argparser(parser)

    parser.add_argument('--sims','--for', action='store', nargs='*',
                                metavar='simulation_name',
                                help='Specify a simulation (or multiple simulations) to run on')

    parser.add_argument('properties', action='store', nargs='+',
                            help="The names of the halo properties to import from the AHF_halos file")

    parser.add_argument('--backwards', action='store_true',
                            help='Process low-z timesteps first')

    args = parser.parse_args()

    db.process_options(args)


    base_sim = db.sim_query_from_name_list(args.sims)

    names = args.properties

    for x in base_sim:
        timesteps = db.core.internal_session.query(db.TimeStep).filter_by(
            simulation_id=x.id, available=True).order_by(db.TimeStep.redshift.desc()).all()

        if args.backwards:
            timesteps = timesteps[::-1]

        for ts in timesteps:
            print "Compiling list for ",ts
            objects = []
            halos = ts.halos.all()
            halos_map = {}
            for h in halos:
                halos_map[h.halo_number] = h

            for values in hsf.iter_halostat(ts, *names):
                halo = halos_map.get(values[0], None)
                if halo is not None:
                    for name, value in zip(names, values[1:]):
                        objects.append((halo, name, value))
            print " ... committing"
            cw.insert_list(objects)
            print " ... done!"

if __name__=="__main__":
    run()