from scripttest import TestFileEnvironment
import re
# from filecmp import cmp

bindir = "graphprot/"
script = "graphprot_seqmodel"
# test file environment
datadir = "test/"
testdir = "test/testenv_graphprot_seqmodel/"
# directories relative to test file environment
bindir_rel = "../../" + bindir
datadir_rel = "../../" + datadir

env = TestFileEnvironment(testdir)


def test_invocation_no_params():
    "Call without parameters should return usage information."
    call = bindir_rel + script
    run = env.run(
        call,
        expect_error=True)
    assert run.returncode == 2
    assert re.match("usage", run.stderr), "stderr should contain usage information: {}".format(run.stderr)


def test_invocation_nonexisting_input():
    "Call with nonexisting input file."
    outfile = "shouldcrash"
    call = bindir_rel + script + " -vvv fit -p {} -n {} --output-dir ./ --model-file {} --n-iter 1".format(
        datadir_rel + "does_not_exist",
        datadir_rel + "does_not_exist",
        outfile,
    )
    run = env.run(
        call,
        expect_error=True,
    )
    assert run.returncode != 0


def test_simple_fit():
    "Train a model on 10 positive and 10 negative sequences using default paramters."
    outfile = "test_simple_fit.model"
    call = bindir_rel + script + " -vvv fit -p {} -n {} --output-dir ./ --model-file {} --n-iter 1".format(
        datadir_rel + "PARCLIP_MOV10_Sievers_10seqs.train.positives.fa",
        datadir_rel + "PARCLIP_MOV10_Sievers_10seqs.train.negatives.fa",
        outfile
    )
    # ../../graphprot/graphprot_seqmodel -vvv fit -p ../../test/PARCLIP_MOV10_Sievers_100seqs.train.positives.fa -n ../../test/PARCLIP_MOV10_Sievers_100seqs.train.negatives.fa --output-dir ./ --model-file test_simple_fit.model --n-iter 1
    env.run(call)
    call = bindir_rel + script + " -vvv estimate -p {} -n {} --output-dir ./ --model-file {} --cross-validation".format(
        datadir_rel + "PARCLIP_MOV10_Sievers_10seqs.train.positives.fa",
        datadir_rel + "PARCLIP_MOV10_Sievers_10seqs.train.negatives.fa",
        outfile
    )
    # ../../graphprot/graphprot_seqmodel -vvv estimate -p ../../test/PARCLIP_MOV10_Sievers_1kseqs.train.positives.fa -n ../../test/PARCLIP_MOV10_Sievers_1kseqs.train.negatives.fa --output-dir ./ --model-file test_simple_fit.model --cross-validation
    run = env.run(
        call,
        expect_stderr=True,
    )
    stdout = open(testdir + outfile + ".cv.out", "w")
    stdout.write(run.stdout)


# def test_manualparams_fit():
#     "Train a model on 10 positive and 10 negative sequences setting parameters to non-default values."
#     outfile = "test_manualparams_fit.model"
#     call = bindir_rel + script + " -vvv fit -p {} -n {} --output-dir ./ --model-file {} --n-iter 1 --nbits 20".format(
#         datadir_rel + "PARCLIP_MOV10_Sievers_10seqs.train.positives.fa",
#         datadir_rel + "PARCLIP_MOV10_Sievers_10seqs.train.negatives.fa",
#         outfile
#     )
#     env.run(call)
#     call = bindir_rel + script + " -vvv estimate -p {} -n {} --output-dir ./ --model-file {} --cross-validation".format(
#         datadir_rel + "PARCLIP_MOV10_Sievers_10seqs.train.positives.fa",
#         datadir_rel + "PARCLIP_MOV10_Sievers_10seqs.train.negatives.fa",
#         outfile
#     )
#     run = env.run(
#         call,
#         expect_stderr=True,
#     )
#     stdout = open(testdir + outfile + ".cv.out", "w")
#     stdout.write(run.stdout)


# def test_optimized_fit():
#     "Train a model on 100 positive and 100 negative sequences, optimize paramters."
#     outfile = "test_optmized_fit.model"
#     call = bindir_rel + script + " -vvv fit -p {} -n {} --output-dir ./ --model-file {} --n-iter 5".format(
#         datadir_rel + "PARCLIP_MOV10_Sievers_100seqs.train.positives.fa",
#         datadir_rel + "PARCLIP_MOV10_Sievers_100seqs.train.negatives.fa",
#         outfile
#     )
#     # ../../graphprot/graphprot_seqmodel -vvv fit -p ../../test/PARCLIP_MOV10_Sievers_100seqs.train.positives.fa -n ../../test/PARCLIP_MOV10_Sievers_100seqs.train.negatives.fa --output-dir ./ --model-file test_optimized_fit.model --n-iter 5
#     env.run(call)
#     call = bindir_rel + script + " -vvv estimate -p {} -n {} --output-dir ./ --model-file {} --cross-validation".format(
#         datadir_rel + "PARCLIP_MOV10_Sievers_100seqs.train.positives.fa",
#         datadir_rel + "PARCLIP_MOV10_Sievers_100seqs.train.negatives.fa",
#         outfile
#     )
#     # ../../graphprot/graphprot_seqmodel -vvv estimate -p ../../test/PARCLIP_MOV10_Sievers_100seqs.train.positives.fa -n ../../test/PARCLIP_MOV10_Sievers_100seqs.train.negatives.fa --output-dir ./ --model-file test_optimized_fit.model --cross-validation
#     run = env.run(
#         call,
#         expect_stderr=True,
#     )
#     stdout = open(testdir + outfile + ".cv.out", "w")
#     stdout.write(run.stdout)
