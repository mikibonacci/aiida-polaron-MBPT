#!/bin/bash

function submit_job {
  
  # $1 ---> name of the batch file
  # $2 ---> string of type of calculation ("dft", "G0W0", ...)
  # $3 ---> id number: use "afterok:$3"
  #                 0: from scratch
  # $4 ---> 0: don't run the job
  #         1: run the job
  
  if [[ $4 -eq 1 ]] ; then
    if [[ $3 -eq 0 ]] ; then
      qsub $1 1> tmp.batch.o 2> tmp.batch.e
    else
      qsub -W depend=afterok:$3 $1 1> tmp.batch.o 2> tmp.batch.e
    fi
    
    error=$(wc -l tmp.batch.e | awk '{print $1}')
    if [[ $error -ne 0 ]] ; then
      echo "Error submiting the job at $2 level"
      cat tmp.batch.e
      exit
    fi
    
    job_id_number=$(cat tmp.batch.o | cut -d. -f1)
    echo $job_id_number > tmp.job_id_number
    
    rm -f tmp.batch.o tmp.batch.e
    if [[ $2 == "dft" ]] ; then
      echo "SCF and nSCF calculations submited with id number: $job_id_number"
    elif [[ $2 == "p2y" ]] ; then
      echo "P2Y calculation submited with id number:           $job_id_number"
    elif [[ $2 == "static-screening" ]] ; then
      echo "Static GoWo calculation submited with id number:   $job_id_number"
    elif [[ $2 == "GoWo" ]] ; then
      echo "GoWo calculations submited with id number:         $job_id_number"
    elif [[ $2 == "merging" ]] ; then
      echo "Merging submited with id number:                   $job_id_number"
    elif [[ $2 == "BSE" ]] ; then
      echo "BSE calculation submited with id number:           $job_id_number"
    fi
  fi
  
}
#===============================================================================
#===============================================================================
function helpout {

 cat <<EOF
 Set and submit the GoWo/BSE calculations for a given polaronic configuration
 Use as: setting_new_configuration.sh -config= <string> --run
 
 where
 
 -config=/--config-name= <string>  name of the polaron configuration;
 -run/--run                        submit calculations on the queue system;
 -merge/--with-merge               perform merging with yambopy and then 
                                   submit a BSE calculation;
 
 Use -help/-h/--help/? to show this help.
  
EOF
}
#===============================================================================
#===============================================================================

config_name="none"
run_jobs=0
merging=0
project_dir="/home/it4i-saviola/project/savio/"

while [[ $# -gt 0 ]] ; do
    case "$1" in
        "--help" | "-h" | "-help" | "?") helpout; exit ;;
        "-config=" | "--config-name=") shift ; config_name=$1; shift ;;
        "-run" | "--run") run_jobs=1; shift ;;
        "--with-merge" | "-merge") merging=1 ; shift ;;
        *) 
            echo "---------------------------------------------------"
            echo " Error:                                            "
            echo "  $1 is a wrong option!                            "
            echo "  See setting_new_configuration.sh -h to choice the"
            echo "  options.                                         "
            echo "---------------------------------------------------"
            exit
            ;;
    esac
done

if [[ ! -d ../template-runs ]] ; then
  echo "Error: ../template-runs directory is required!"
  exit
fi

if [[ ! -e scf.in ]] ; then
  echo "Error: scf.in file is required!"
  exit
fi

if [[ $config_name == "none" ]] ; then
  echo "Error: a configuration name must be provided by command line"
  exit
fi

if [[ -d $config_name ]] ; then
  echo "Warning: directory $config_name has already been created!"
  echo "         To avoid losing data the script will not procede!"
  exit
fi

if [[ -d ${project_dir}/tio2-3nb/config1/${config_name} ]] ; then
  echo "Warning: directory $config_name has already been created in"
  echo "                                                           "
  echo "         ${project_dir}/tio2-3nb/config1/                  "
  echo "                                                           "
  echo "         No need to proceed!                               "
  exit
fi 

cp -r ../template-runs $config_name


cd ${config_name}/dft/

cp ../../scf.in .


# change the pseudo path in scf.in --------------------------------------------
# 
for iline in $(seq 1 50) ; do
  string=$(sed -n ${iline}p scf.in | awk '{print $1}')
  if [[ $string == "pseudo_dir" ]] ; then
    line_where_to_cut=$(echo "${iline} - 1" | bc)
  fi
done

nlines_scf_file=$(wc -l scf.in | awk '{print $1}')
remaining_lines=$(echo "${nlines_scf_file} - ${line_where_to_cut} - 1" | bc)

head -n $line_where_to_cut scf.in > tmp1
tail -n $remaining_lines scf.in > tmp2

echo "  pseudo_dir                = '/home/it4i-saviola/pseudo/samaneh/'," >> tmp1

cat tmp1 tmp2 > tmp3

mv tmp3 scf.in
rm -f tmp1 tmp2


# delete the hubbard keywords -------------------------------------------------
# 
sed -i -e "/lda_plus_u/d" scf.in
sed -i -e "/Hubbard_U/d" scf.in


# Check force_symmorphic = .true. ---------------------------------------------
# 
is_symmorphic_forced=$(grep "force_symmorphic" scf.in | awk '{print $3}' | sed -e "s/\.//g")
if [[ $is_symmorphic_forced == "false" ]] ; then
  sed -i -e "s/force_symmorphic          = \.false\./force_symmorphic          = \.true\./g" scf.in
fi


# Remove possible nbnd keyword in scf.in --------------------------------------
# 
sed -i -e "/nbnd /d" scf.in


# create and change the nscf.in input file ------------------------------------
# 
cp scf.in nscf.in
sed -i -e "s/scf/nscf/g" nscf.in
sed -i -e "s/smearing/fixed/g" nscf.in
sed -i -e "/degauss/d" nscf.in

for iline in $(seq 1 100) ; do
  string=$(sed -n ${iline}p nscf.in | awk '{print $1}')
  if [[ $string == "ecutrho" ]] ; then
    line_where_to_cut=$(echo "${iline}" | bc)
  fi
done

nlines_scf_file=$(wc -l nscf.in | awk '{print $1}')
remaining_lines=$(echo "${nlines_scf_file} - ${line_where_to_cut}" | bc)

head -n $line_where_to_cut nscf.in > tmp1
tail -n $remaining_lines nscf.in > tmp2

echo "  nbnd                      = 3500" >> tmp1

cat tmp1 tmp2 > tmp3

mv tmp3 nscf.in
rm -f tmp1 tmp2

sed -i -e "s/= 'restart'/= 'from_scratch'/g" scf.in


# Change submitting batch files and submit calculation if run_jobs=1 ----------
#  
sed -i -e "s/STRING_TO_REPLACE/${config_name}/g" batch_qe
sed -i -e "s/STRING_TO_REPLACE/${config_name}/g" batch_p2y

submit_job "batch_qe" "dft" 0 $run_jobs
if [[ -e tmp.job_id_number ]] ; then
  dft_job_id_number=$(cat tmp.job_id_number)
  rm -f tmp.job_id_number
fi

submit_job "batch_p2y" "p2y" $dft_job_id_number $run_jobs
if [[ -e tmp.job_id_number ]] ; then
  p2y_job_id_number=$(cat tmp.job_id_number)
  rm -f tmp.job_id_number
fi


# Change submiting batch files and submit calculations for GoWo ---------------
# 
cd ../yambo/static-screening/
rm -f ../README
sed -i -e "s/STRING_TO_REPLACE/${config_name}/g" batch
psave=$(grep "psave=" batch | cut -d= -f2 | sed -e "s/\"//g")
if [[ ! -d $psave ]] ; then
  echo "Error: no $psave directory found!"
  exit
fi

submit_job "batch" "static-screening" $p2y_job_id_number $run_jobs
if [[ -e tmp.job_id_number ]] ; then
  static_job_id_number=$(cat tmp.job_id_number)
  rm -f tmp.job_id_number
fi

cd ../gowo/
sed -i -e "s/STRING_TO_REPLACE/${config_name}/g" batch_set
psave=$(grep "psave=" batch_set | cut -d= -f2 | sed -e "s/\"//g")
if [[ ! -d $psave ]] ; then
  echo "Error: no $psave directory found!"
  exit
fi

submit_job "batch_set" "GoWo" $static_job_id_number $run_jobs
if [[ -e tmp.job_id_number ]] ; then
  gowo_job_id_number=$(cat tmp.job_id_number)
  rm -f tmp.job_id_number
fi

if [[ $merging -eq 1 ]] ; then
  sed -i -e "s/STRING_TO_REPLACE/${config_name}/g" batch_merge
  
  submit_job "batch_merge" "merging" $gowo_job_id_number $run_jobs
  if [[ -e tmp.job_id_number ]] ; then
    merging_job_id_number=$(cat tmp.job_id_number)
    rm -f tmp.job_id_number
  fi
else
  rm -f batch_merge
fi


# Change submiting batch files and submit calculations for BSE ----------------
# 
cd ../bse/q0-111_config_806v-1056c/
sed -i -e "s/STRING_TO_REPLACE/${config_name}/g" batch
psave=$(grep "psave=" batch | cut -d= -f2 | sed -e "s/\"//g")
if [[ ! -d $psave ]] ; then
  echo "Error: no $psave directory found!"
  exit
fi
path_db=$(grep "path_db=" batch | cut -d= -f2 | sed -e "s/\"//g")
if [[ ! -d $path_db ]] ; then
  echo "Error: no $path_db directory found!"
  exit
fi


if [[ $merging -eq 1 ]] ; then
  submit_job "batch" "BSE" $merging_job_id_number $run_jobs
  if [[ -e tmp.job_id_number ]] ; then
    bse_job_id_number=$(cat tmp.job_id_number)
    rm -f tmp.job_id_number
  fi
fi


# Removing the original scf.in SCF input file from the main directory ---------
# 
rm -f ../../../../scf.in
cd ../../../../
